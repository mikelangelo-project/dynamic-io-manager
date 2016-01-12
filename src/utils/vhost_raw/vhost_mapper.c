#include <stdio.h>
#include <unistd.h>
#include <errno.h>
#include <fcntl.h>
#include <string.h>

#include "vhost_raw.h"

static const char * const stats_file_path = "/sys/class/vhost/%s/%s/stats_ptr";

static u64 __vhost_stats_kernel(const char * const fname)
{
    FILE *file;
    ssize_t read;
    u64 kernel_address = 0UL;

    printf("%s:%d\n", __func__, __LINE__);
    if((file = fopen(fname, "r")) == NULL) {
        fprintf(stderr, "Couldn't open file: %s, error: %s\n", fname, strerror(errno));
        return 0UL;
    }
    printf("%s:%d\n", __func__, __LINE__);
    if ((read = fscanf(file, "%llx\n", &kernel_address)) <= 0) {
        fprintf(stderr, "Couldn't read file: %s, error: %s\n", fname, strerror(errno));
        return 0UL;
    }
    printf("%s:%d\n", __func__, __LINE__);
    fclose(file);
    printf("%s:%d\n", __func__, __LINE__);

    return kernel_address;
}

static u64 vhost_stats_kernel(const char * const dir, const char * const id)
{
    char buf[256] = {0};

    printf("%s:%d\n", __func__, __LINE__);
    if (snprintf(buf, 255, stats_file_path, dir, id) < 0){
       fprintf(stderr, "failed creating the file name.\n");
       return 0UL;
    }

    printf("%s:%d\n", __func__, __LINE__);
    if(access(buf, F_OK) == -1) {
        fprintf(stderr, "file not found: %s\n", buf);
        return 0UL;
    }
    printf("%s:%d\n", __func__, __LINE__);
    return __vhost_stats_kernel(buf);
}

u64 vhost_worker_stats_kernel(const char * const id)
{
    return vhost_stats_kernel("worker", id);
}

u64 vhost_device_stats_kernel(const char * const id)
{
    return vhost_stats_kernel("dev", id);
}

u64 vhost_virtqueue_stats_kernel(const char * const id)
{
    return vhost_stats_kernel("vq", id);
}