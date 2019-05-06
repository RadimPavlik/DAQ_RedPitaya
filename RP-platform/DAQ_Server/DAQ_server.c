/*
FPGA Project: DAQ
Server for setting configuration and reading data from FPGA

Created by Pavlik Radim 7.1.2019
*/

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <math.h>
#include <sys/mman.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <time.h>
#include <errno.h>


#define START 1
#define STOP 0

#define N_SAMPLES 65536

// Command frames structure from client app:
//FRAME: [31 30 29 28 27 26 25 24 23 22 21 20 19 18 17 16 15 14 13 12 11 10 9 8 7 6 5 4 3 2 1 0]
#define COMMAND_INDEX_OFFSET 29  //Available bits: [31 30 29] = 8 frame types

#define COMMAND_INDEX_TYPE_START 0
#define COMMAND_INDEX_TYPE_STOP 3
#define COMMAND_INDEX_TYPE_TRIGGER_LVL 1
#define COMMAND_INDEX_TYPE_PRETRIGGER_VAL 2
#define COMMAND_INDEX_TYPE_CHANNEL_SELECT 4
#define COMMAND_INDEX_TYPE_FORCE_TRIGGER 5
//2-more left => decimation,...

#define COMMAND_TRIGGER_LVL_RANGE 0xffff    //[16 15 14 13 12 11 10 9 8 7 6 5 4 3 2 1 0]
#define COMMAND_TRIGGER_LVL_SIGN_BIT 0x8000 //[16]
#define COMMAND_PRETRIGGER_VAL_RANGE 0x1fff //[13 12 11 10 9 8 7 6 5 4 3 2 1 0]
#define COMMAND_FORCE_TRIGGER_RANGE 0x1     //[0]
#define COMMAND_CHANNEL_SELECT_RANGE 0x1    //[0]

// Buffer structure on RP side:
//________|S__S__S___TRIGGER_LVL(int)___________________|_______PRETRIGGER_VAL(uint)_______|_.............|
//BUFFER: [31 30 29 28 27 26 25 24 23 22 21 20 19 18 17 | 16 15 14 13 12 11 10 9 8 7 6 5 4 | 3 | 2 | 1 | 0]
#define RP_BUFFER_MEASURING_START_OFFSET 0
#define RP_BUFFER_FORCE_TRIGGER_OFFSET 1
#define RP_BUFFER_CHANNEL_SELECT_OFFSET 2
#define RP_BUFFER_PRETRIGGER_VAL_OFFSET 3
#define RP_BUFFER_TRIGGER_LVL_OFFSET 16



int main(int argc, char *argv[])
{
  int fd, j, sock_server, sock_client, size, yes = 1, nsmpl, rx;
  void *cfg, *dat;
  char *name = "/dev/mem";
  int16_t TrigLvl =0;
  uint16_t SignHelp=0;
  uint16_t PreTrig=0; //PreTrig max 13bit unsigned number
  
  bool ForceTrigger_b = false;
  bool Channel_two_b = false; //if not true then active channel is channel one(CH1)

  struct sockaddr_in addr;
  uint32_t command, tmp;
  uint16_t buffer[65540]; // 65536 places, sizeof 16bit (for uint32_t 32768)
  clock_t time_begin;
  double time_spent;
  int measuring = 0;
  int StopMeasurement = 0;


  if((fd = open(name, O_RDWR)) < 0)
  {
    perror("open");
    return EXIT_FAILURE;
  }

  dat = mmap(NULL, (256*1024) , PROT_READ|PROT_WRITE, MAP_SHARED, fd, 0x40000000); //size due to VIVADO 256K //RP Data Register 
  cfg = mmap(NULL, (4*1024) , PROT_READ|PROT_WRITE, MAP_SHARED, fd, 0x42000000); //size due to VIVADO 4K //RP Config Register



  if((sock_server = socket(AF_INET, SOCK_STREAM, 0)) < 0)
  {
    perror("socket");
    return EXIT_FAILURE;
  }

  setsockopt(sock_server, SOL_SOCKET, SO_REUSEADDR, (void *)&yes , sizeof(yes));

  /* setup listening address */
  memset(&addr, 0, sizeof(addr));
  addr.sin_family = AF_INET;
  addr.sin_addr.s_addr = htonl(INADDR_ANY);
  addr.sin_port = htons(1001);

  if(bind(sock_server, (struct sockaddr *)&addr, sizeof(addr)) < 0)
  {
    perror("bind");
    return EXIT_FAILURE;
  }

  listen(sock_server, 1024); // second argument = defines the maximum length to which the queue of pending connections for sockfd may grow.
  //add possible wait function to wait 1s to be able to see message if started via shell script
  //sleep(1);
  printf("\nDAQ Server V1.1 is running\n");
  printf("Listening on port 1001 ...\n");


  while(1)
  {
    printf("--Waiting for connection!--\n"); 
    if((sock_client = accept(sock_server, NULL, NULL)) < 0)
    {  
	   perror("accept");
	   return EXIT_FAILURE;
    }
    while(1) //MSG_WAITALL
    {     
      rx = recv(sock_client, (char *)&command, 4, MSG_DONTWAIT);
      if (rx < 0 && errno != EAGAIN) 
      {
         measuring = 0;
         StopMeasurement = 0;
	       printf("rx<0\n");
	       break;
      }
      if(rx > 0) 
      {
	       //printf("--Something received:--\n");
         switch(command >> COMMAND_INDEX_OFFSET) // looking at [31 30 29] - from binary client communication frame (3 bity)
         {
            case COMMAND_INDEX_TYPE_TRIGGER_LVL:  //Trigger Level
  				    TrigLvl = (command & COMMAND_TRIGGER_LVL_RANGE); 
              printf("Trigger level setup obtained: %d\n", TrigLvl);

              SignHelp = (TrigLvl & COMMAND_TRIGGER_LVL_SIGN_BIT); //select sign of 16bit integer 
              TrigLvl = TrigLvl | (SignHelp | SignHelp>>1 | SignHelp>>2); //Padding of sign mark to 3 higest bits => due to vivado design logic ([S S S][DATA_14b])
              //printf("Trigger level after RP conversion to 14bit %d, hex:%#010x \n", TrigLvl,TrigLvl);

  				    
				    break;

            case COMMAND_INDEX_TYPE_PRETRIGGER_VAL: //Pretrigger window
              PreTrig =  (command & COMMAND_PRETRIGGER_VAL_RANGE); //only 13 bits //cannot be number higher than 13bits of log.(1)
    
              /* //this method was used when PreTrig was intiger
              if(PreTrig < 0) //cannot be negative value
              {
                PreTrig = 0;
              }
              */
  				    printf("Length of Pretrigger window setup obtained: %d\n",  PreTrig);
				    break;
            
            case COMMAND_INDEX_TYPE_STOP: //STOP MEASURING
              printf("Measurement Stop command received\n");
              //set StopMeasurement to true
              measuring = 0;
              StopMeasurement = 1;
            break;

            case COMMAND_INDEX_TYPE_CHANNEL_SELECT: //Channel Select //maybe could be better to include this into single data frame to reduce redundant almost empty frames 
             Channel_two_b = (command & COMMAND_CHANNEL_SELECT_RANGE);
             if(Channel_two_b)
             {
               printf("Channel 2 selected\n");
             }
             else printf("Channel 1 selected\n");
             
             //PickUptheChannel
            break;

            case COMMAND_INDEX_TYPE_FORCE_TRIGGER: //Forced Trigger
             ForceTrigger_b = (command & COMMAND_FORCE_TRIGGER_RANGE);
             if(ForceTrigger_b)
             {
               printf("Forced trigger ON\n");
             }
             else printf("Forced trigger OFF\n");
            break;

            case COMMAND_INDEX_TYPE_START: /* fire */ // enable DAQ
              //printf("Fire-command received for %d trigger level, %d pretrigger length\n ",TrigLvl,PreTrig); 
				      *((int32_t *)(cfg + 0)) = (STOP) + (ForceTrigger_b << RP_BUFFER_FORCE_TRIGGER_OFFSET) + (Channel_two_b << RP_BUFFER_CHANNEL_SELECT_OFFSET) + ((PreTrig) << RP_BUFFER_PRETRIGGER_VAL_OFFSET) + (TrigLvl << RP_BUFFER_TRIGGER_LVL_OFFSET); 
				      //time_begin = clock(); // Uncomment if wanted to measure time between acqusitions on RP-platform
              //Memory check: is data stored correctly
              /*
              printf(" status of memory 0x42000000 %#010x before\n", (*((uint32_t *)(cfg )) & 0xffffffff) );
				      printf(" Trigger Value 0x42000000 %#010x \n", (*((uint32_t *)(cfg )) & 0xffff<<16) );
              printf(" PreTrigger Value 0x42000000 %#010x \n", (*((uint32_t *)(cfg )) & 0xffff<<1) );
              */
              //Start measurement
              *((int32_t *)(cfg + 0)) ^= 1; //invert RP_BUFFER_MEASURING_START_OFFSET bit => measuring initiated
              //printf(" status of memory 0x42000000 %#010x after\n", (*((uint32_t *)(cfg )) & 0xffffffff) );
				      measuring = 1;
				    break;

			      default: //nothing
				      printf("This should not happen! Check the offset/range of frame indexes in client app or endianity\n");
				    break;
         }
      }

      if(StopMeasurement == 1)
      {
        StopMeasurement = 0;
        break;
      }

      /* Check if it is in measuring mode and has finished */
      if (measuring == 1 && ((*((uint32_t *)(cfg + 8)) & 1) != 0) ) //checking adress GPIO2 0x42000008 if measurement completed. ? looking for 1 
      { 
        //printf("Measuring finished \n");
      	//time_spent = ((double)(clock() - time_begin)) / CLOCKS_PER_SEC; // measure time // Uncomment if wanted to measure time between acqusitions on RP-platform
        send(sock_client, dat, 2*N_SAMPLES, MSG_NOSIGNAL); //send data via reference/adress to dat- mapped space
        //test if send not valid then break?

      	//printf("%d samples measured in %f s\n", N_SAMPLES, time_spent); // Uncomment if wanted to measure time between acqusitions on RP-platform
		    measuring = 0;
		    //break; //Commented in oreder to stop terminating connection after single acqisiton.
      }
    }	
    //printf("Socket Client Closed1\n");
    close(sock_client);
   
  }
  //printf("Socket Server Closed2\n");
  close(sock_server);
  return EXIT_SUCCESS;
}
