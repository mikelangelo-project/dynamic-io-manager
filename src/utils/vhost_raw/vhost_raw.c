#include <Python.h>
#include "structmember.h"

#include "vhost_raw.h"
#include "kernel_mapper.h"

#define VHOST_STAT_GETTER_FUNC(elem, stat) \
static u64 elem##_get_##stat(elem *self) \
{                                       \
    return self->stats->stat;           \
}

#define VHOST_STAT(elem, stat, disc) \
    {#stat, (PyCFunction) elem##_get_##stat, METH_NOARGS, disc}

// ------------------ vhost worker ---------------------------------------------
typedef struct {
    PyObject_HEAD
    char *id;
    struct vhost_worker_stats *stats;
} VhostWorker;

static void VhostWorker_dealloc(VhostWorker* self)
{
    unmap(self->stats);
    self->ob_type->tp_free((PyObject*)self);
}

static PyObject *
VhostWorker_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    VhostWorker *self;

    self = (VhostWorker *)type->tp_alloc(type, 0);
    if (self != NULL) {
        self->id = "";
        self->stats = NULL;
    }
    return (PyObject *)self;
}

static int
VhostWorker_init(VhostWorker *self, PyObject *args, PyObject *kwds)
{
    static char *kwlist[] = {"id", NULL};
    if (! PyArg_ParseTupleAndKeywords(args, kwds, "s", kwlist, &self->id))
        return -1;
    self->stats = remap_vhost_worker(self->id);
    return 0;
}

VHOST_STAT_GETTER_FUNC(VhostWorker, loops)
VHOST_STAT_GETTER_FUNC(VhostWorker, enabled_interrupts)
VHOST_STAT_GETTER_FUNC(VhostWorker, cycles)
VHOST_STAT_GETTER_FUNC(VhostWorker, mm_switches)
VHOST_STAT_GETTER_FUNC(VhostWorker, wait)
VHOST_STAT_GETTER_FUNC(VhostWorker, empty_works)
VHOST_STAT_GETTER_FUNC(VhostWorker, empty_polls)
VHOST_STAT_GETTER_FUNC(VhostWorker, stuck_works)
VHOST_STAT_GETTER_FUNC(VhostWorker, noqueue_works)
VHOST_STAT_GETTER_FUNC(VhostWorker, pending_works)
VHOST_STAT_GETTER_FUNC(VhostWorker, last_loop_tsc_end)
VHOST_STAT_GETTER_FUNC(VhostWorker, poll_cycles)
VHOST_STAT_GETTER_FUNC(VhostWorker, notif_cycles)
VHOST_STAT_GETTER_FUNC(VhostWorker, total_work_cycles)
VHOST_STAT_GETTER_FUNC(VhostWorker, ksoftirq_occurrences)
VHOST_STAT_GETTER_FUNC(VhostWorker, ksoftirq_time)
VHOST_STAT_GETTER_FUNC(VhostWorker, ksoftirqs)

static PyMethodDef VhostWorker_methods[] = {
    VHOST_STAT(VhostWorker, loops, "number of loops performed"),
    VHOST_STAT(VhostWorker, enabled_interrupts, "number of times interrupts were re-enabled"),
    VHOST_STAT(VhostWorker, cycles, "cycles spent in the worker, excluding cycles doing queue work"),
    VHOST_STAT(VhostWorker, mm_switches, "number of times the mm was switched"),
    VHOST_STAT(VhostWorker, wait, "number of cycles the worker thread was not running after schedule"),
    VHOST_STAT(VhostWorker, empty_works, "number of times there were no works in the queue -- ignoring poll kicks"),
    VHOST_STAT(VhostWorker, empty_polls, "number of times there were no queues to poll and the polling queue was not empty"),
    VHOST_STAT(VhostWorker, stuck_works, "number of times were detected stuck and limited queues"),
    VHOST_STAT(VhostWorker, noqueue_works, "number of works which have no queue related to them (e.g. vhost-net rx)"),
    VHOST_STAT(VhostWorker, pending_works, "number of pending works"),
    VHOST_STAT(VhostWorker, last_loop_tsc_end, "tsc when the last loop was performed"),
    VHOST_STAT(VhostWorker, poll_cycles, "cycles spent handling kicks in poll mode"),
    VHOST_STAT(VhostWorker, notif_cycles, "cycles spent handling works in notif mode"),
    VHOST_STAT(VhostWorker, total_work_cycles, "total cycles spent handling works"),
    VHOST_STAT(VhostWorker, ksoftirq_occurrences, "number of times a softirq occured during worker work"),
    VHOST_STAT(VhostWorker, ksoftirq_time, "time (ns) that softirq process took while worker processed its work"),
    VHOST_STAT(VhostWorker, ksoftirqs, "the number of softirq interruts handled during worker processed its work"),
    {NULL}
};

static PyMemberDef VhostWorker_members[] = {
    {"worker_id", T_STRING, offsetof(VhostWorker, id), 0, "worker id"},
    {NULL}  /* Sentinel */
};

static PyTypeObject VhostWorkerType = {
    PyObject_HEAD_INIT(NULL)
    0,                                        /*ob_size*/
    "vhost_raw.VhostWorker",                  /*tp_name*/
    sizeof(VhostWorker),                      /*tp_basicsize*/
    0,                                        /*tp_itemsize*/
    (destructor)VhostWorker_dealloc,          /*tp_dealloc*/
    0,                                        /*tp_print*/
    0,                                        /*tp_getattr*/
    0,                                        /*tp_setattr*/
    0,                                        /*tp_compare*/
    0,                                        /*tp_repr*/
    0,                                        /*tp_as_number*/
    0,                                        /*tp_as_sequence*/
    0,                                        /*tp_as_mapping*/
    0,                                        /*tp_hash */
    0,                                        /*tp_call*/
    0,                                        /*tp_str*/
    0,                                        /*tp_getattro*/
    0,                                        /*tp_setattro*/
    0,                                        /*tp_as_buffer*/
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE, /*tp_flags*/
    "Vhost raw worker statistics objects",    /* tp_doc */
    0,                                        /* tp_traverse */
    0,                                        /* tp_clear */
    0,                                        /* tp_richcompare */
    0,                                        /* tp_weaklistoffset */
    0,                                        /* tp_iter */
    0,                                        /* tp_iternext */
    VhostWorker_methods,                      /* tp_methods */
    VhostWorker_members,                      /* tp_members */
    0,                                        /* tp_getset */
    0,                                        /* tp_base */
    0,                                        /* tp_dict */
    0,                                        /* tp_descr_get */
    0,                                        /* tp_descr_set */
    0,                                        /* tp_dictoffset */
    (initproc)VhostWorker_init,               /* tp_init */
    0,                                        /* tp_alloc */
    VhostWorker_new,                          /* tp_new */
};

// ------------------ vhost device ---------------------------------------------

typedef struct {
    PyObject_HEAD
    char *id;
    struct vhost_device_stats *stats;
} VhostDevice;

static void VhostDevice_dealloc(VhostDevice* self)
{
    unmap(self->stats);
    self->ob_type->tp_free((PyObject*)self);
}

static PyObject *
VhostDevice_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    VhostDevice *self;

    self = (VhostDevice *)type->tp_alloc(type, 0);
    if (self != NULL) {
        self->id = "";
        self->stats = NULL;
    }
    return (PyObject *)self;
}

static int
VhostDevice_init(VhostDevice *self, PyObject *args, PyObject *kwds)
{
    static char *kwlist[] = {"id", NULL};
    if (! PyArg_ParseTupleAndKeywords(args, kwds, "s", kwlist, &self->id))
        return -1;
    self->stats = remap_vhost_device(self->id);
    return 0;
}

VHOST_STAT_GETTER_FUNC(VhostDevice, delay_per_work)
VHOST_STAT_GETTER_FUNC(VhostDevice, delay_per_kbyte)
VHOST_STAT_GETTER_FUNC(VhostDevice, device_move_total)
VHOST_STAT_GETTER_FUNC(VhostDevice, device_move_count)
VHOST_STAT_GETTER_FUNC(VhostDevice, device_detach)
VHOST_STAT_GETTER_FUNC(VhostDevice, device_attach)

static PyMethodDef VhostDevice_methods[] = {
    VHOST_STAT(VhostDevice, delay_per_work, "the number of loops per work we have to delay the calculation."),
    VHOST_STAT(VhostDevice, delay_per_kbyte, "the number of loops per kbyte we have to delay the calculation."),
    VHOST_STAT(VhostDevice, device_move_total, ""),
    VHOST_STAT(VhostDevice, device_move_count, ""),
    VHOST_STAT(VhostDevice, device_detach, ""),
    VHOST_STAT(VhostDevice, device_attach, ""),
    {NULL}
};

static PyMemberDef VhostDevice_members[] = {
    {"dev_id", T_STRING, offsetof(VhostDevice, id), 0, "device id"},
    {NULL}  /* Sentinel */
};

static PyTypeObject VhostDeviceType = {
    PyObject_HEAD_INIT(NULL)
    0,                                        /*ob_size*/
    "vhost_raw.VhostDevice",                  /*tp_name*/
    sizeof(VhostDevice),                      /*tp_basicsize*/
    0,                                        /*tp_itemsize*/
    (destructor)VhostDevice_dealloc,          /*tp_dealloc*/
    0,                                        /*tp_print*/
    0,                                        /*tp_getattr*/
    0,                                        /*tp_setattr*/
    0,                                        /*tp_compare*/
    0,                                        /*tp_repr*/
    0,                                        /*tp_as_number*/
    0,                                        /*tp_as_sequence*/
    0,                                        /*tp_as_mapping*/
    0,                                        /*tp_hash */
    0,                                        /*tp_call*/
    0,                                        /*tp_str*/
    0,                                        /*tp_getattro*/
    0,                                        /*tp_setattro*/
    0,                                        /*tp_as_buffer*/
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE, /*tp_flags*/
    "Vhost raw device statistics objects",    /* tp_doc */
    0,                                        /* tp_traverse */
    0,                                        /* tp_clear */
    0,                                        /* tp_richcompare */
    0,                                        /* tp_weaklistoffset */
    0,                                        /* tp_iter */
    0,                                        /* tp_iternext */
    VhostDevice_methods,                      /* tp_methods */
    VhostDevice_members,                      /* tp_members */
    0,                                        /* tp_getset */
    0,                                        /* tp_base */
    0,                                        /* tp_dict */
    0,                                        /* tp_descr_get */
    0,                                        /* tp_descr_set */
    0,                                        /* tp_dictoffset */
    (initproc)VhostDevice_init,               /* tp_init */
    0,                                        /* tp_alloc */
    VhostDevice_new,                          /* tp_new */
};

// ------------------ vhost virtqueue ------------------------------------------
typedef struct {
    PyObject_HEAD
    char *id;
    struct vhost_virtqueue_stats *stats;
} VhostVirtqueue;

static void VhostVirtqueue_dealloc(VhostWorker* self)
{
    unmap(self->stats);
    self->ob_type->tp_free((PyObject*)self);
}

static PyObject *
VhostVirtqueue_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    VhostVirtqueue *self;

    self = (VhostVirtqueue *)type->tp_alloc(type, 0);
    if (self != NULL) {
        self->id = "";
        self->stats = NULL;
    }
    return (PyObject *)self;
}

static int
VhostVirtqueue_init(VhostVirtqueue *self, PyObject *args, PyObject *kwds)
{
    static char *kwlist[] = {"vq_id", NULL};
    if (! PyArg_ParseTupleAndKeywords(args, kwds, "s", kwlist, &self->id))
        return -1;
    self->stats = remap_vhost_virtqueue(self->id);
    return 0;
}

VHOST_STAT_GETTER_FUNC(VhostVirtqueue, poll_kicks)
VHOST_STAT_GETTER_FUNC(VhostVirtqueue, poll_cycles)
VHOST_STAT_GETTER_FUNC(VhostVirtqueue, poll_bytes)
VHOST_STAT_GETTER_FUNC(VhostVirtqueue, poll_wait)
VHOST_STAT_GETTER_FUNC(VhostVirtqueue, poll_empty)
VHOST_STAT_GETTER_FUNC(VhostVirtqueue, poll_empty_cycles)
VHOST_STAT_GETTER_FUNC(VhostVirtqueue, poll_coalesced)
VHOST_STAT_GETTER_FUNC(VhostVirtqueue, poll_limited)
VHOST_STAT_GETTER_FUNC(VhostVirtqueue, poll_pending_cycles)
VHOST_STAT_GETTER_FUNC(VhostVirtqueue, notif_works)
VHOST_STAT_GETTER_FUNC(VhostVirtqueue, notif_cycles)
VHOST_STAT_GETTER_FUNC(VhostVirtqueue, notif_bytes)
VHOST_STAT_GETTER_FUNC(VhostVirtqueue, notif_wait)
VHOST_STAT_GETTER_FUNC(VhostVirtqueue, notif_limited)
VHOST_STAT_GETTER_FUNC(VhostVirtqueue, ring_full)
VHOST_STAT_GETTER_FUNC(VhostVirtqueue, stuck_times)
VHOST_STAT_GETTER_FUNC(VhostVirtqueue, stuck_cycles)
VHOST_STAT_GETTER_FUNC(VhostVirtqueue, last_poll_tsc_end)
VHOST_STAT_GETTER_FUNC(VhostVirtqueue, last_notif_tsc_end)
VHOST_STAT_GETTER_FUNC(VhostVirtqueue, last_poll_empty_tsc)
VHOST_STAT_GETTER_FUNC(VhostVirtqueue, handled_bytes)
VHOST_STAT_GETTER_FUNC(VhostVirtqueue, was_limited)

static PyMethodDef VhostVirtqueue_methods[] = {
    VHOST_STAT(VhostVirtqueue, poll_kicks, "number of kicks in poll mode"),
    VHOST_STAT(VhostVirtqueue, poll_cycles, "cycles spent handling kicks in poll mode"),
    VHOST_STAT(VhostVirtqueue, poll_bytes, "bytes sent/received by kicks in poll mode"),
    VHOST_STAT(VhostVirtqueue, poll_wait, "cycles elapsed between poll kicks"),
    VHOST_STAT(VhostVirtqueue, poll_empty, "number of times the queue was empty during poll"),
    VHOST_STAT(VhostVirtqueue, poll_empty_cycles, "number of cycles elapsed while the queue was empty"),
    VHOST_STAT(VhostVirtqueue, poll_coalesced, "number of times this queue was coalesced"),
    VHOST_STAT(VhostVirtqueue, poll_limited, "number of times the queue was limited by netweight during poll kicks"),
    VHOST_STAT(VhostVirtqueue, poll_pending_cycles, "cycles elapsed between item arrival and poll"),
    VHOST_STAT(VhostVirtqueue, notif_works, "cycles spent handling works in notif mode"),
    VHOST_STAT(VhostVirtqueue, notif_cycles, "cycles spent handling works in notif mode"),
    VHOST_STAT(VhostVirtqueue, notif_bytes, "bytes sent/received by works in notif mode"),
    VHOST_STAT(VhostVirtqueue, notif_wait, "cycles elapsed between work arrival and handling in notif mode"),
    VHOST_STAT(VhostVirtqueue, notif_limited, "number of times the queue was limited by netweight in notif mode"),
    VHOST_STAT(VhostVirtqueue, ring_full, "number of times the ring was full"),
    VHOST_STAT(VhostVirtqueue, stuck_times, "how many times this queue was stuck and limited other queues"),
    VHOST_STAT(VhostVirtqueue, stuck_cycles, "total amount of cycles the queue was stuck"),
    VHOST_STAT(VhostVirtqueue, last_poll_tsc_end, "tsc when the last poll finished"),
    VHOST_STAT(VhostVirtqueue, last_notif_tsc_end, "tsc when the last notif finished"),
    VHOST_STAT(VhostVirtqueue, last_poll_empty_tsc, "tsc when the queue was detected empty for the first time"),
    VHOST_STAT(VhostVirtqueue, handled_bytes, "number of bytes handled by this queue in the last poll/notif. Must be updated by the concrete vhost implementations (vhost-net)"),
    VHOST_STAT(VhostVirtqueue, was_limited, "flag indicating if the queue was limited by net-weight during the last poll/notif. Must be updated by the concrete vhost implementations (vhost-net)"),
    {NULL}
};

static PyMemberDef VhostVirtqueue_members[] = {
    {"vq_id", T_STRING, offsetof(VhostVirtqueue, id), 0, "virtual queue id"},
    {NULL}  /* Sentinel */
};

static PyTypeObject VhostVirtqueueType = {
    PyObject_HEAD_INIT(NULL)
    0,                                        /*ob_size*/
    "vhost_raw.VhostVirtqueue",               /*tp_name*/
    sizeof(VhostVirtqueue),                   /*tp_basicsize*/
    0,                                        /*tp_itemsize*/
    (destructor)VhostVirtqueue_dealloc,       /*tp_dealloc*/
    0,                                        /*tp_print*/
    0,                                        /*tp_getattr*/
    0,                                        /*tp_setattr*/
    0,                                        /*tp_compare*/
    0,                                        /*tp_repr*/
    0,                                        /*tp_as_number*/
    0,                                        /*tp_as_sequence*/
    0,                                        /*tp_as_mapping*/
    0,                                        /*tp_hash */
    0,                                        /*tp_call*/
    0,                                        /*tp_str*/
    0,                                        /*tp_getattro*/
    0,                                        /*tp_setattro*/
    0,                                        /*tp_as_buffer*/
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE, /*tp_flags*/
    "Vhost raw virtqueue statistics objects", /* tp_doc */
    0,                                        /* tp_traverse */
    0,                                        /* tp_clear */
    0,                                        /* tp_richcompare */
    0,                                        /* tp_weaklistoffset */
    0,                                        /* tp_iter */
    0,                                        /* tp_iternext */
    VhostVirtqueue_methods,                   /* tp_methods */
    VhostVirtqueue_members,                   /* tp_members */
    0,                                        /* tp_getset */
    0,                                        /* tp_base */
    0,                                        /* tp_dict */
    0,                                        /* tp_descr_get */
    0,                                        /* tp_descr_set */
    0,                                        /* tp_dictoffset */
    (initproc)VhostVirtqueue_init,            /* tp_init */
    0,                                        /* tp_alloc */
    VhostVirtqueue_new,                       /* tp_new */
};


// ------------------ vhost module ---------------------------------------------

static PyMethodDef vhost_raw_methods[] = {
    {NULL}  /* Sentinel */
};

#ifndef PyMODINIT_FUNC	/* declarations for DLL import/export */
#define PyMODINIT_FUNC void
#endif
PyMODINIT_FUNC
initvhost_raw(void)
{
    PyObject* m;

    if (PyType_Ready(&VhostWorkerType) < 0)
        return;
    if (PyType_Ready(&VhostDeviceType) < 0)
        return;
    if (PyType_Ready(&VhostVirtqueueType) < 0)
        return;

    m = Py_InitModule3("vhost_raw", vhost_raw_methods,
                       "vhost raw module, remapped kernel memory.");

    if (m == NULL)
      return;

    Py_INCREF(&VhostWorkerType);
    PyModule_AddObject(m, "VhostWorker", (PyObject *)&VhostWorkerType);
    Py_INCREF(&VhostDeviceType);
    PyModule_AddObject(m, "VhostDevice", (PyObject *)&VhostDeviceType);
    Py_INCREF(&VhostVirtqueueType);
    PyModule_AddObject(m, "VhostVirtqueue", (PyObject *)&VhostVirtqueueType);
}