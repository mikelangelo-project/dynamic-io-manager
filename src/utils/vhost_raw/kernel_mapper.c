#include <stdio.h>
#include <unistd.h>
#include <errno.h>
#include <fcntl.h>
#include <string.h>
#include <sys/mman.h>

#include "kernel_mapper.h"

void *kernel_remap(u64 kernel_address){
    FILE *file;
    long page_size = sysconf(_SC_PAGESIZE);
    u64 mmap_offset = kernel_address & ~(page_size-1);
    char *mapped;
    void *ret;

    printf("%s:%d\n", __func__, __LINE__);
    if(kernel_address < 0xc0000000UL) {
	    fprintf(stderr, "illegal variable kernel address: 0x%llx\n", kernel_address);
	    return NULL;
    }

    printf("%s:%d\n", __func__, __LINE__);
    if((file = fopen("/dev/kmem", "r")) == NULL) {
	    fprintf(stderr, "failed open()ing /dev/kmem: %s\n", strerror(errno));
	    return NULL;
    }
    printf("%s:%d\n", __func__, __LINE__);
    if((mapped = mmap(NULL, PAGE_SIZE, PROT_READ, MAP_SHARED, fileno(file),
        mmap_offset)) ==  MAP_FAILED ) {
	    fprintf(stderr, "user-kernel map failed: %s\n", strerror(errno));
	    return NULL;
    }
    printf("%s:%d\n", __func__, __LINE__);
    fclose(file);
    printf("%s:%d\n", __func__, __LINE__);

    ret = (void *)(mapped + (kernel_address - mmap_offset));
    printf("%s:%d\n", __func__, __LINE__);
    return ret;
}

void unmap(void *addr){
    long page_size = sysconf(_SC_PAGESIZE);
    munmap(addr, page_size);
}