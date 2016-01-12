#include <stdio.h>
#include <unistd.h>
#include <stdlib.h>
#include <errno.h>
#include <fcntl.h>
#include <string.h>
#include <sys/syscall.h>

#include "copy_to_user.h"
#define SYS_COPY_TO_USER 316

int copy_to_user(void *to, u64 ka, size_t len)
{
    printf("%s:%d\n", __func__, __LINE__);
    if(syscall(SYS_COPY_TO_USER, to, (void *)ka, len) == -1) {
        fprintf(stderr, "failed to copy_to_usr(%p, 0x%llx, %lu): %s\n",
            to, ka, len, strerror(errno));
        return 0;
    }
    printf("%s:%d\n", __func__, __LINE__);
    return 1;
}