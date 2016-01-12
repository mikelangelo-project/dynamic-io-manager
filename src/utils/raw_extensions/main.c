#include <stdio.h>
#include <unistd.h>
#include <stdlib.h>
#include <errno.h>
#include <fcntl.h>
#include <string.h>
#include <sys/syscall.h>
#include <time.h>

#include "vhost_raw.h"

#define SYS_COPY_TO_USER 316

static inline long long unsigned time_ns(struct timespec* const ts) {
  if (clock_gettime(CLOCK_REALTIME, ts)) {
    exit(1);
  }
  return ((long long unsigned) ts->tv_sec) * 1000000000LLU
    + (long long unsigned) ts->tv_nsec;
}

int main() {
    const char * const id = "w.1";
    struct vhost_worker_stats w;
    u64 ka = vhost_worker_stats_kernel(id);
    const int iterations = 10000000;
    struct timespec ts;

    printf("%s: ka: %llu\n", id, ka);
    if (ka == 0UL){
        return 1;
    }

    const long long unsigned start_ns = time_ns(&ts);
    for (int i = 0; i < iterations; i++) {
        if(syscall(SYS_COPY_TO_USER, &w, (void *)ka, sizeof(w)) == -1) {
            return 1;
        }
    }
    const long long unsigned delta = time_ns(&ts) - start_ns;
    printf("%i system calls in %lluns (%.1fns/syscall)\n",
         iterations, delta, (delta / (float) iterations));
    printf("%s: total_work_cycles: %llu\n", id, w.total_work_cycles);
    return 0;
}
