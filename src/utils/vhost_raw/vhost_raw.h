#ifndef _VHOST_STATS_H
#define _VHOST_STATS_H
#include "kernel_mapper.h"

struct vhost_virtqueue_stats {
    u64 poll_kicks; /* number of kicks in poll mode */
    u64 poll_cycles; /* cycles spent handling kicks in poll mode */
    u64 poll_bytes; /* bytes sent/received by kicks in poll mode */
    u64 poll_wait; /* cycles elapsed between poll kicks */
    u64 poll_empty; /* number of times the queue was empty during poll */
    u64 poll_empty_cycles; /* number of cycles elapsed while the queue was empty */
    u64 poll_coalesced; /* number of times this queue was coalesced */
    u64 poll_limited; /* number of times the queue was limited by netweight during poll kicks*/
    u64 poll_pending_cycles; /* cycles elapsed between item arrival and poll */

    u64 notif_works; /* number of works in notif mode */
    u64 notif_cycles; /* cycles spent handling works in notif mode */
    u64 notif_bytes; /* bytes sent/received by works in notif mode */
    u64 notif_wait; /* cycles elapsed between work arrival and handling in notif mode */
    u64 notif_limited; /* number of times the queue was limited by netweight in notif mode */

    u64 ring_full; /* number of times the ring was full */

    u64 stuck_times; /* how many times this queue was stuck and limited other queues */
    u64 stuck_cycles; /* total amount of cycles the queue was stuck */

    u64 last_poll_tsc_end; /* tsc when the last poll finished */
    u64 last_notif_tsc_end; /* tsc when the last notif finished */
    u64 last_poll_empty_tsc; /* tsc when the queue was detected empty for the first time */
    u64 handled_bytes; /* number of bytes handled by this queue in the last poll/notif. Must be updated by the concrete vhost implementations (vhost-net)*/
    u64 was_limited; /* flag indicating if the queue was limited by net-weight during the last poll/notif. Must be updated by the concrete vhost implementations (vhost-net)*/

    u64 ksoftirq_occurrences; /* number of times a softirq occured during the processing of this queue */
    u64 ksoftirq_time; /* time (ns) that softirq occured during the processing of this queue */
    u64 ksoftirqs; /* the number of softirq interruts handled during the processing of this queue */
};

struct vhost_device_stats {
    u64 delay_per_work; /* the number of loops per work we have to delay the calculation. */
    u64 delay_per_kbyte; /* the number of loops per kbyte we have to delay the calculation. */
    u64 device_move_total;
    u64 device_move_count;
    u64 device_detach;
    u64 device_attach;
};

struct vhost_worker_stats {
    u64 loops; /* number of loops performed */
    u64 enabled_interrupts; /* number of times interrupts were re-enabled */
    u64 cycles; /* cycles spent in the worker, excluding cycles doing queue work */
    u64 mm_switches; /* number of times the mm was switched */
    u64 wait; /* number of cycles the worker thread was not running after schedule */
    u64 empty_works; /* number of times there were no works in the queue -- ignoring poll kicks  */
    u64 empty_polls; /* number of times there were no queues to poll and the polling queue was not empty  */
    u64 stuck_works; /* number of times were detected stuck and limited queues */
    u64 noqueue_works; /* number of works which have no queue related to them (e.g. vhost-net rx) */
    u64 pending_works; /* number of pending works */

    u64 last_loop_tsc_end; /* tsc when the last loop was performed */

    u64 poll_cycles; /* cycles spent handling kicks in poll mode */
    u64 notif_cycles; /* cycles spent handling works in notif mode */
    u64 total_work_cycles; /* total cycles spent handling works */

    u64 ksoftirq_occurrences; /* number of times a softirq occured during worker work */
    u64 ksoftirq_time; /* time (ns) that softirq process took while worker processed its work */
    u64 ksoftirqs; /* the number of softirq interruts handled during worker processed its work */

    u64 ixgbe_poll_cycles; /* cycles spent polling on the ixgbe interfaces */
    u64 ixgbe_poll_last_loop_tsc_end; /* tsc when the last ixgbe poll was performed */
    u64 ixgbe_poll_last_non_empty_loop_tsc_end; /* tsc when the last ixgbe poll that was not empty performed */
    u64 ixgbe_poll_wait; /* cycles elapsed between polls */
    u64 ixgbe_poll_empty; /* number of times the queue was empty during ixgbe poll */
    u64 ixgbe_poll_empty_cycles; /* number of cycles elapsed while the ixgbe poll queues were empty */

    u64 ixgbe_poll_total_packets; /* number of packets polled from the ixgbe interface */
    u64 ixgbe_poll_loops;
};

struct vhost_worker_stats *remap_vhost_worker(const char * const id);
struct vhost_device_stats *remap_vhost_device(const char * const id);
struct vhost_virtqueue_stats *remap_vhost_virtqueue(const char * const id);

#endif /* _VHOST_STATS_H */


