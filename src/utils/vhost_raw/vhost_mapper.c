#include <stdio.h>
#include <unistd.h>
#include <errno.h>
#include <fcntl.h>
#include <string.h>

#include "vhost_raw.h"
#include "kernel_mapper.h"

static const char * const stats_file_path = "/sys/class/vhost/%s/%s/stats_ptr";

static void *__vhost_remap(const char * const fname)
{
    FILE *file;
    ssize_t read;
    u64 kernel_address = 0UL;

    printf("%s:%d\n", __func__, __LINE__);
    if((file = fopen(fname, O_RDONLY)) == NULL) {
        fprintf(stderr, "Couldn't open file: %s, error: %s\n", fname, strerror(errno));
        return NULL;
    }
    printf("%s:%d\n", __func__, __LINE__);
    if ((read = fscanf(file, "%llx\n", &kernel_address)) <= 0) {
        fprintf(stderr, "Couldn't read file: %s, error: %s\n", fname, strerror(errno));
        return NULL;
    }
    printf("%s:%d\n", __func__, __LINE__);
    fclose(file);
    printf("%s:%d\n", __func__, __LINE__);

    return kernel_remap(kernel_address);
}

static void *vhost_remap(const char * const dir, const char * const id)
{
    char buf[256] = {0};

    printf("%s:%d\n", __func__, __LINE__);
    if (snprintf(buf, 255, stats_file_path, dir, id) < 0){
       fprintf(stderr, "failed creating the file name.\n");
       return NULL;
    }

    printf("%s:%d\n", __func__, __LINE__);
    if(access(buf, F_OK) == -1) {
        fprintf(stderr, "file not found: %s\n", buf);
        return NULL;
    }
    printf("%s:%d\n", __func__, __LINE__);
    return __vhost_remap(buf);
}

struct vhost_worker_stats *remap_vhost_worker(const char * const id)
{
    printf("%s:%d\n", __func__, __LINE__);
    return (struct vhost_worker_stats *)vhost_remap("worker", id);
}

struct vhost_device_stats *remap_vhost_device(const char * const id)
{
    return (struct vhost_device_stats *)vhost_remap("dev", id);
}

struct vhost_virtqueue_stats *remap_vhost_virtqueue(const char * const id)
{
    return (struct vhost_virtqueue_stats *)vhost_remap("vq", id);
}
