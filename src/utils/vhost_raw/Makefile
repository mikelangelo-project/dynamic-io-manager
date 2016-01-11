# Makefile template for shared library

CC = gcc # C compiler
CFLAGS = -fPIC -Wall -Wextra -O0 -g # C flags
LDFLAGS = -shared # linking flags
RM = rm -f # rm command
TARGET_LIB = libvhost.so # target lib

SRCS = vhost_mapper.c vhost_raw.c kernel_mapper.c # source files
OBJS = $(SRCS:.c=.o)

.PHONY: all
all: ${TARGET_LIB}

$(TARGET_LIB): $(OBJS)
	$(CC) ${LDFLAGS} -o $@ $^

$(SRCS:.c=.d):%.d:%.c
	$(CC) $(CFLAGS) -MM $< >$@

include $(SRCS:.c=.d)

.PHONY: clean
clean:
	-${RM} ${TARGET_LIB} ${OBJS} $(SRCS:.c=.d)