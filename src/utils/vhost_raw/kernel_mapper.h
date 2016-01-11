#ifndef _KERNEL_MAPPER_H
#define _KERNEL_MAPPER_H

typedef unsigned long long  u64;
#define PAGE_SIZE 4096

void *kernel_remap(u64 kernel_address);

#endif /* _KERNEL_MAPPER_H */