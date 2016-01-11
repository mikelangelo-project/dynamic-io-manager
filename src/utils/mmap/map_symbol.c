#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>
#include <errno.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/types.h>
#include <sys/stat.h>




#define PAGE_SIZE 4096
#define JIFFIES_ADDRESS_CMD "grep ' jiffies_Rsmp' /proc/ksyms|cut -d' ' -f1"
#define ERROR(format, args...) error__( (format) ,##args)


//------------------------------------------------------------------------------
//
//------------------------------------------------------------------------------
void error__(const char* format, ...)
    //    __attribute__ ((format (printf,1,2)))
{
    va_list args;
    va_start(args, format);

    fprintf(stderr, "ERROR: ");
    vfprintf(stderr, format, args);
    fprintf(stderr, "\n");

    va_end(args);
    exit( EXIT_FAILURE );
}


//------------------------------------------------------------------------------
//
//------------------------------------------------------------------------------
volatile
unsigned long *map_jiffies(void)
{
    // vars:
    volatile u_long *retval = NULL;
    int              fd;
    void            *mapped = NULL;
    FILE            *infile;
    char             addrstr[32];
    u_long           jiffies_offset = 0;
    u_long           mmap_offset;
    u_long           mmap_size;


    //
    // 1- get the `jiffies' address
    //
    if( (infile = popen(JIFFIES_ADDRESS_CMD, "r")) == NULL ) {
	ERROR("popen(\"%s\") failed: %s\n", JIFFIES_ADDRESS_CMD,
	      strerror(errno));
    }

    if( feof(infile) ) {
	ERROR("jiffies symbol wasn't found in the kernel!\n"
	      "(are you using the correct kernel?)\n");
    }

    fscanf(infile, "%s", addrstr);

    if( pclose(infile) ) {
	ERROR("pclose failed (child did not exit gracefully)\n");
    }

    jiffies_offset = strtoul(addrstr, NULL, 16);
    mmap_offset    = jiffies_offset & ~(PAGE_SIZE-1);
    mmap_size      = PAGE_SIZE;

    if(jiffies_offset < 0xc0000000) {
	ERROR("illegal variable kernel address: 0x%08lx\n", jiffies_offset);
    }


    //
    // 2- map the kernel to uesr address:
    //
    if( (fd = open("/dev/kmem", O_RDONLY)) == -1 ) {
	ERROR("failed open()ing /dev/kmem: %s\n", strerror(errno));
    }
    if( (mapped = mmap(NULL,mmap_size,PROT_READ,MAP_SHARED,fd,mmap_offset))
	 ==  MAP_FAILED ) {
	ERROR("user-kernel map failed: %s\n", strerror(errno));
    }
    close(fd);


    //
    // 3- reverse the page alignment process
    //
    retval = (unsigned long*)(mapped + (jiffies_offset - mmap_offset));
    return retval;
}

int main()
{
    volatile unsigned long *jiffies =  map_jiffies();
    printf("jiffies[%p]=%lu\n", jiffies, *jiffies);
    return 0;
}
