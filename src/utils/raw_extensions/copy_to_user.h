#ifndef _COPY_TO_USER_H
#define _COPY_TO_USER_H

typedef unsigned long long  u64;
int copy_to_user(void *to, u64 ka, size_t len);

#endif /* _COPY_TO_USER_H */