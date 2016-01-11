#include <stdio.h>
#include <unistd.h>
#include <errno.h>
#include <fcntl.h>
#include <string.h>
#include <sys/mman.h>

#include "kernel_mapper.h"

void *kernel_remap(u64 kernel_address){
    FILE *file;
    u64 mmap_offset = kernel_address & ~(PAGE_SIZE-1);
    u64 mmap_size = PAGE_SIZE;
    char *mapped;
    void *ret;

    if(kernel_address < 0xc0000000UL) {
	    fprintf(stderr, "illegal variable kernel address: 0x%llx\n", kernel_address);
	    return NULL;
    }

    if((file = fopen("/dev/kmem", O_RDONLY)) == NULL) {
	    fprintf(stderr, "failed open()ing /dev/kmem: %s\n", strerror(errno));
	    return NULL;
    }
    if((mapped = mmap(NULL, mmap_size, PROT_READ, MAP_SHARED, fileno(file),
        mmap_offset)) ==  MAP_FAILED ) {
	    fprintf(stderr, "user-kernel map failed: %s\n", strerror(errno));
	    return NULL;
    }
    fclose(file);

    ret = (void *)(mapped + (kernel_address - mmap_offset));
    return ret;
}
