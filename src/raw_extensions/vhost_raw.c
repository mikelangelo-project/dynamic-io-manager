#include <Python.h>
#include "structmember.h"

#include "copy_to_user.h"
#include "vhost_raw.h"

#define VHOST_STAT(elem, stats_type, stat, disc) \
    {#stat, T_LONGLONG, offsetof(elem, stats) + offsetof(stats_type, stat), 0, disc}

// ------------------ vhost worker ---------------------------------------------
typedef struct {
    PyObject_HEAD
    char *id;
    u64 kernel_address;
    struct vhost_worker_stats stats;
} VhostWorker;

static void VhostWorker_dealloc(VhostWorker* self)
{
    self->ob_type->tp_free((PyObject*)self);
}

static PyObject *
VhostWorker_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    VhostWorker *self;

    self = (VhostWorker *)type->tp_alloc(type, 0);
    printf("%s:%d\n", __func__, __LINE__);
    if (self != NULL) {
        self->id = "";
        self->kernel_address = 0;
        printf("%s:%d\n", __func__, __LINE__);
    }
    printf("%s:%d\n", __func__, __LINE__);
    return (PyObject *)self;
}

static int
VhostWorker_init(VhostWorker *self, PyObject *args, PyObject *kwds)
{
    static char *kwlist[] = {"id", NULL};
    printf("%s:%d\n", __func__, __LINE__);
    if (! PyArg_ParseTupleAndKeywords(args, kwds, "s", kwlist, &self->id))
        return -1;
    printf("%s:%d\n", __func__, __LINE__);
    self->kernel_address = vhost_worker_stats_kernel(self->id);
    printf("%s:%d\n", __func__, __LINE__);
    if (self->kernel_address != 0UL){
        printf("%s:%d\n", __func__, __LINE__);
        copy_to_user(&self->stats, self->kernel_address, sizeof(self->stats));
        printf("%s:%d\n", __func__, __LINE__);
    }
    printf("%s:%d\n", __func__, __LINE__);
    return 0;
}

static PyObject *
VhostWorker_update(VhostWorker *self){
    if (self->kernel_address != 0UL){
        copy_to_user(&self->stats, self->kernel_address, sizeof(self->stats));
    }
    return (PyObject*)self;
}

static PyMethodDef VhostWorker_methods[] = {
    {"update", (PyCFunction) VhostWorker_update, METH_NOARGS, "update stats"},
    {NULL}
};

#define VHOST_WORKER_STAT(stat, disc) \
    VHOST_STAT(VhostWorker, struct vhost_worker_stats, stat, disc)

static PyMemberDef VhostWorker_members[] = {
    {"worker_id", T_STRING, offsetof(VhostWorker, id), 0, "worker id"},
    VHOST_WORKER_STAT(loops, "number of loops performed"),
    VHOST_WORKER_STAT(enabled_interrupts, "number of times interrupts were re-enabled"),
    VHOST_WORKER_STAT(cycles, "cycles spent in the worker, excluding cycles doing queue work"),
    VHOST_WORKER_STAT(mm_switches, "number of times the mm was switched"),
    VHOST_WORKER_STAT(wait, "number of cycles the worker thread was not running after schedule"),
    VHOST_WORKER_STAT(empty_works, "number of times there were no works in the queue -- ignoring poll kicks"),
    VHOST_WORKER_STAT(empty_polls, "number of times there were no queues to poll and the polling queue was not empty"),
    VHOST_WORKER_STAT(stuck_works, "number of times were detected stuck and limited queues"),
    VHOST_WORKER_STAT(noqueue_works, "number of works which have no queue related to them (e.g. vhost-net rx)"),
    VHOST_WORKER_STAT(pending_works, "number of pending works"),
    VHOST_WORKER_STAT(last_loop_tsc_end, "tsc when the last loop was performed"),
    VHOST_WORKER_STAT(poll_cycles, "cycles spent handling kicks in poll mode"),
    VHOST_WORKER_STAT(notif_cycles, "cycles spent handling works in notif mode"),
    VHOST_WORKER_STAT(total_work_cycles, "total cycles spent handling works"),
    VHOST_WORKER_STAT(ksoftirq_occurrences, "number of times a softirq occured during worker work"),
    VHOST_WORKER_STAT(ksoftirq_time, "time (ns) that softirq process took while worker processed its work"),
    VHOST_WORKER_STAT(ksoftirqs, "the number of softirq interruts handled during worker processed its work"),
    {NULL}
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
    u64 kernel_address;
    struct vhost_device_stats stats;
} VhostDevice;

static void VhostDevice_dealloc(VhostDevice* self)
{
    self->ob_type->tp_free((PyObject*)self);
}

static PyObject *
VhostDevice_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    VhostDevice *self;

    self = (VhostDevice *)type->tp_alloc(type, 0);
    if (self != NULL) {
        self->id = "";
        self->kernel_address = 0UL;
    }
    return (PyObject *)self;
}

static int
VhostDevice_init(VhostDevice *self, PyObject *args, PyObject *kwds)
{
    static char *kwlist[] = {"id", NULL};
    if (! PyArg_ParseTupleAndKeywords(args, kwds, "s", kwlist, &self->id))
        return -1;
    self->kernel_address = vhost_device_stats_kernel(self->id);
    if (self->kernel_address != 0UL){
        copy_to_user(&self->stats, self->kernel_address, sizeof(self->stats));
    }
    return 0;
}

static PyObject *
VhostDevice_update(VhostDevice *self){
    if (self->kernel_address != 0UL){
        copy_to_user(&self->stats, self->kernel_address, sizeof(self->stats));
    }
    return (PyObject*)self;
}

static PyMethodDef VhostDevice_methods[] = {
    {"update", (PyCFunction) VhostDevice_update, METH_NOARGS, "update stats"},
    {NULL}
};

#define VHOST_DEVICE_STAT(stat, disc) \
    VHOST_STAT(VhostDevice, struct vhost_device_stats, stat, disc)

static PyMemberDef VhostDevice_members[] = {
    {"dev_id", T_STRING, offsetof(VhostDevice, id), 0, "device id"},
    VHOST_DEVICE_STAT(delay_per_work, "the number of loops per work we have to delay the calculation."),
    VHOST_DEVICE_STAT(delay_per_kbyte, "the number of loops per kbyte we have to delay the calculation."),
    VHOST_DEVICE_STAT(device_move_total, ""),
    VHOST_DEVICE_STAT(device_move_count, ""),
    VHOST_DEVICE_STAT(device_detach, ""),
    VHOST_DEVICE_STAT(device_attach, ""),
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
    u64 kernel_address;
    struct vhost_virtqueue_stats stats;
} VhostVirtqueue;

static void VhostVirtqueue_dealloc(VhostWorker* self)
{
    self->ob_type->tp_free((PyObject*)self);
}

static PyObject *
VhostVirtqueue_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    VhostVirtqueue *self;

    self = (VhostVirtqueue *)type->tp_alloc(type, 0);
    if (self != NULL) {
        self->id = "";
        self->kernel_address = 0UL;
    }
    return (PyObject *)self;
}

static int
VhostVirtqueue_init(VhostVirtqueue *self, PyObject *args, PyObject *kwds)
{
    static char *kwlist[] = {"vq_id", NULL};
    if (! PyArg_ParseTupleAndKeywords(args, kwds, "s", kwlist, &self->id))
        return -1;
    self->kernel_address = vhost_virtqueue_stats_kernel(self->id);
    if (self->kernel_address != 0UL){
        copy_to_user(&self->stats, self->kernel_address, sizeof(self->stats));
    }
    return 0;
}

static PyObject *
VhostVirtqueue_update(VhostVirtqueue *self){
    if (self->kernel_address != 0UL){
        copy_to_user(&self->stats, self->kernel_address, sizeof(self->stats));
    }
    return (PyObject *)self;
}

static PyMethodDef VhostVirtqueue_methods[] = {
    {"update", (PyCFunction) VhostVirtqueue_update, METH_NOARGS, "update stats"},
    {NULL}
};

#define VHOST_VQ_STAT(stat, disc) \
    VHOST_STAT(VhostVirtqueue, struct vhost_virtqueue_stats, stat, disc)

static PyMemberDef VhostVirtqueue_members[] = {
    {"vq_id", T_STRING, offsetof(VhostVirtqueue, id), 0, "virtual queue id"},
    VHOST_VQ_STAT(poll_kicks, "number of kicks in poll mode"),
    VHOST_VQ_STAT(poll_cycles, "cycles spent handling kicks in poll mode"),
    VHOST_VQ_STAT(poll_bytes, "bytes sent/received by kicks in poll mode"),
    VHOST_VQ_STAT(poll_wait, "cycles elapsed between poll kicks"),
    VHOST_VQ_STAT(poll_empty, "number of times the queue was empty during poll"),
    VHOST_VQ_STAT(poll_empty_cycles, "number of cycles elapsed while the queue was empty"),
    VHOST_VQ_STAT(poll_coalesced, "number of times this queue was coalesced"),
    VHOST_VQ_STAT(poll_limited, "number of times the queue was limited by netweight during poll kicks"),
    VHOST_VQ_STAT(poll_pending_cycles, "cycles elapsed between item arrival and poll"),
    VHOST_VQ_STAT(notif_works, "cycles spent handling works in notif mode"),
    VHOST_VQ_STAT(notif_cycles, "cycles spent handling works in notif mode"),
    VHOST_VQ_STAT(notif_bytes, "bytes sent/received by works in notif mode"),
    VHOST_VQ_STAT(notif_wait, "cycles elapsed between work arrival and handling in notif mode"),
    VHOST_VQ_STAT(notif_limited, "number of times the queue was limited by netweight in notif mode"),
    VHOST_VQ_STAT(ring_full, "number of times the ring was full"),
    VHOST_VQ_STAT(stuck_times, "how many times this queue was stuck and limited other queues"),
    VHOST_VQ_STAT(stuck_cycles, "total amount of cycles the queue was stuck"),
    VHOST_VQ_STAT(last_poll_tsc_end, "tsc when the last poll finished"),
    VHOST_VQ_STAT(last_notif_tsc_end, "tsc when the last notif finished"),
    VHOST_VQ_STAT(last_poll_empty_tsc, "tsc when the queue was detected empty for the first time"),
    VHOST_VQ_STAT(handled_bytes, "number of bytes handled by this queue in the last poll/notif. Must be updated by the concrete vhost implementations (vhost-net)"),
    VHOST_VQ_STAT(was_limited, "flag indicating if the queue was limited by net-weight during the last poll/notif. Must be updated by the concrete vhost implementations (vhost-net)"),
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
    printf("%s:%d\n", __func__, __LINE__);

    if (PyType_Ready(&VhostWorkerType) < 0)
        return;
    printf("%s:%d\n", __func__, __LINE__);

    if (PyType_Ready(&VhostDeviceType) < 0)
        return;
    printf("%s:%d\n", __func__, __LINE__);

    if (PyType_Ready(&VhostVirtqueueType) < 0)
        return;
    printf("%s:%d\n", __func__, __LINE__);

    m = Py_InitModule3("vhost_raw", vhost_raw_methods,
                       "vhost raw module, remapped kernel memory.");
    printf("%s:%d\n", __func__, __LINE__);
    if (m == NULL)
      return;
    printf("%s:%d\n", __func__, __LINE__);

    Py_INCREF(&VhostWorkerType);
    printf("%s:%d\n", __func__, __LINE__);
    PyModule_AddObject(m, "VhostWorker", (PyObject *)&VhostWorkerType);
    printf("%s:%d\n", __func__, __LINE__);
    Py_INCREF(&VhostDeviceType);
    printf("%s:%d\n", __func__, __LINE__);
    PyModule_AddObject(m, "VhostDevice", (PyObject *)&VhostDeviceType);
    printf("%s:%d\n", __func__, __LINE__);
    Py_INCREF(&VhostVirtqueueType);
    printf("%s:%d\n", __func__, __LINE__);
    PyModule_AddObject(m, "VhostVirtqueue", (PyObject *)&VhostVirtqueueType);
}