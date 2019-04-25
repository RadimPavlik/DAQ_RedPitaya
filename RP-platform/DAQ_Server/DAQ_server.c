/*
FPGA Project: DAQ
Server for setting configuration and reading data from FPGA

Created by Pavlik Radim 7.1.2019
*/

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
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

int main(int argc, char *argv[])
{
  int fd, j, sock_server, sock_client, size, yes = 1, nsmpl, triglvl, pretrig, rx;
  void *cfg, *dat;
  char *name = "/dev/mem";
  int16_t TrigLvl =0, PreTrig=0;
  //PreTrig max 15bit neznaminkove cislo?

  struct sockaddr_in addr;
  uint32_t command, value, tmp;
  uint16_t buffer[65540]; // 65536 pozic po 16 bitech (pro uint32_t 32768)
  clock_t time_begin;
  double time_spent;
  int measuring = 0;
  int StopMeasurement = 0;


  if((fd = open(name, O_RDWR)) < 0)
  {
    perror("open");
    return EXIT_FAILURE;
  }

  dat = mmap(NULL, (256*1024) , PROT_READ|PROT_WRITE, MAP_SHARED, fd, 0x40000000); //podle velikosti z VIVADA 256K 
  cfg = mmap(NULL, (4*1024) , PROT_READ|PROT_WRITE, MAP_SHARED, fd, 0x42000000); //podle velikosti z VIVADA 4K 



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

  listen(sock_server, 1024); // druhý argument = defines the maximum length to which the queue of pending connections for sockfd may grow.
  //add possible wait function to wait 1s to be able to see message if started via shell script
  //sleep(1);
  printf("Listening on port 1001 ...\n");


  while(1)
  {
    printf("--Inside Infinite Loop!--\n");
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
         value = command & 0xffffffff; //puvodne 0xfffffff
         switch(command >> 30) // koukam na pozice [31 30] - z binarniho ramce (2 bity) //puvodne 28 - 4 bity
         {
            case 1:  //Trigger Level
  				    //timing = command & 0xff; 
  				    TrigLvl = (command & 0xffff); //(command & 0xfffe);
  				    printf("Trigger level setup obtained %d\n", TrigLvl);
				    break;

            case 2: //Pretrigger window
  				    PreTrig =  (command & 0xffff); //nsamples = (command & 0xff);
              if(PreTrig < 0) //cannot be negative value
              {
                PreTrig = 0;
              }
  				    printf("Length of Pretrigger window setup obtained %d\n",  PreTrig);
				    break;
            
            case 3: //STOP MEASURING
              printf("Measurement Stop command received\n");
              //set StopMeasurement to true
              measuring = 0;
              StopMeasurement = 1;
            break;

            case 0: /* fire */ // enable DAQ
              printf("Fire-command received for %d trigger level, %d pretrigger length\n",TrigLvl,PreTrig);
				      //set trigger and NSAMPLES set NAVERAGES and stop measurement
				      *((int32_t *)(cfg + 0)) = (STOP) + (PreTrig<<1) + (TrigLvl<<16);
				      //sleep(0.1); // wait 0.1 second
				      time_begin = clock();
				      // start measurement
              //Memory check: is data stored correctly
              //printf(" status of memory 0x42000000 %#010x before\n", (*((uint32_t *)(cfg )) & 1) );
              printf(" status of memory 0x42000000 %#010x before\n", (*((uint32_t *)(cfg )) & 0xffffffff) );
				      printf(" Trigger Value 0x42000000 %#010x \n", (*((uint32_t *)(cfg )) & 0xffff<<16) );
              printf(" PreTrigger Value 0x42000000 %#010x \n", (*((uint32_t *)(cfg )) & 0xffff<<1) );
              *((int32_t *)(cfg + 0)) ^= 1;
              //printf(" status of memory 0x42000000 %#010x after\n", (*((uint32_t *)(cfg )) & 1) );
              printf(" status of memory 0x42000000 %#010x before\n", (*((uint32_t *)(cfg )) & 0xffffffff) );
				      measuring = 1;
				    break;

			      default: //nothing
				      printf("This should not happen!\n");
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
      	time_spent = ((double)(clock() - time_begin)) / CLOCKS_PER_SEC; // measure time
	
        send(sock_client, dat, 2*N_SAMPLES, MSG_NOSIGNAL); //send data via reference/adress to dat- mapped space
        //test if send not valid then break?

      	printf("%d samples measured in %f s\n", N_SAMPLES, time_spent);
		    measuring = 0;
		    //break; //zakomentovano at neukoncuje spojeni po jedne akvizici
      }
    }	
    printf("Socket Client Closed1\n");
    close(sock_client);
   
  }
  printf("Socket Server Closed2\n");
  close(sock_server);
  return EXIT_SUCCESS;
}
