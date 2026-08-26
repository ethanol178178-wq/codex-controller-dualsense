/*
 * DS5 Vibe Hub virtual Precision Touchpad.
 * UMDF HID request handling is derived from Microsoft's vhidmini2 sample.
 */
#include "driver.h"

#define PTP_FINGER_COLLECTION_RESET \
    0x05, 0x0d, 0x09, 0x22, 0xa1, 0x02, \
    0x25, 0x01, 0x09, 0x47, 0x09, 0x42, \
    0x95, 0x02, 0x75, 0x01, 0x81, 0x02, \
    0x75, 0x01, 0x95, 0x06, 0x81, 0x03, \
    0x95, 0x01, 0x75, 0x20, 0x27, 0xff, 0xff, 0xff, 0xff, \
    0x09, 0x51, 0x81, 0x02, \
    0x05, 0x01, 0x26, 0x20, 0x4e, 0x75, 0x10, \
    0x55, 0x0e, 0x65, 0x11, \
    0x09, 0x30, 0x46, 0x14, 0x05, 0x95, 0x01, 0x81, 0x02, \
    0x46, 0x52, 0x03, 0x26, 0xe0, 0x2e, 0x09, 0x31, 0x81, 0x02, \
    0x45, 0x00, 0x55, 0x00, 0x65, 0x00, 0xc0

#define PTP_FINGER_COLLECTION_INHERIT \
    0x05, 0x0d, 0x09, 0x22, 0xa1, 0x02, \
    0x25, 0x01, 0x09, 0x47, 0x09, 0x42, \
    0x95, 0x02, 0x75, 0x01, 0x81, 0x02, \
    0x75, 0x01, 0x95, 0x06, 0x81, 0x03, \
    0x95, 0x01, 0x75, 0x20, 0x27, 0xff, 0xff, 0xff, 0xff, \
    0x09, 0x51, 0x81, 0x02, \
    0x05, 0x01, 0x26, 0x20, 0x4e, 0x75, 0x10, \
    0x55, 0x0e, 0x65, 0x11, \
    0x09, 0x30, 0x46, 0x14, 0x05, 0x95, 0x01, 0x81, 0x02, \
    0x46, 0x52, 0x03, 0x26, 0xe0, 0x2e, 0x09, 0x31, 0x81, 0x02, \
    0xc0

HID_REPORT_DESCRIPTOR G_DefaultReportDescriptor[] = {
    /* Five-contact PTP TLC adapted from PeronGH/BLE-PTP-PoC. */
    0x05, 0x0d, 0x09, 0x05, 0xa1, 0x01,
    0x85, REPORT_ID_TOUCHPAD,
    PTP_FINGER_COLLECTION_RESET,
    PTP_FINGER_COLLECTION_RESET,
    PTP_FINGER_COLLECTION_INHERIT,
    PTP_FINGER_COLLECTION_RESET,
    PTP_FINGER_COLLECTION_INHERIT,
    0x55, 0x0c, 0x66, 0x01, 0x10,
    0x47, 0xff, 0xff, 0x00, 0x00,
    0x27, 0xff, 0xff, 0x00, 0x00,
    0x05, 0x0d, 0x09, 0x56, 0x81, 0x02,
    0x09, 0x54, 0x25, 0x7f, 0x75, 0x08, 0x81, 0x02,
    0x05, 0x09, 0x09, 0x01, 0x25, 0x01, 0x75, 0x01, 0x95, 0x01, 0x81, 0x02,
    0x75, 0x01, 0x95, 0x07, 0x81, 0x03,

    /* Contact maximum and pad type (clickpad). */
    0x05, 0x0d, 0x85, REPORT_ID_MAX_COUNT,
    0x09, 0x55, 0x09, 0x59, 0x15, 0x00, 0x26, 0xff, 0x00,
    0x75, 0x08, 0x95, 0x02, 0xb1, 0x02,

    /* Required certification-status feature report. */
    0x06, 0x00, 0xff, 0x85, REPORT_ID_CERTIFICATION,
    0x09, 0xc5, 0x15, 0x00, 0x26, 0xff, 0x00,
    0x75, 0x08, 0x96, 0x00, 0x01, 0xb1, 0x02,
    0xc0,

    /* Precision Touchpad configuration TLC. */
    0x05, 0x0d, 0x09, 0x0e, 0xa1, 0x01,
    0x85, REPORT_ID_INPUT_MODE, 0x09, 0x22, 0xa1, 0x02,
    0x09, 0x52, 0x15, 0x00, 0x25, DS5PTP_CONTACT_COUNT,
    0x75, 0x08, 0x95, 0x01, 0xb1, 0x02,
    0xc0,
    0xa1, 0x00, 0x85, REPORT_ID_FUNCTION_SWITCH,
    0x09, 0x57, 0x09, 0x58, 0x75, 0x01, 0x95, 0x02, 0x25, 0x01, 0xb1, 0x02,
    0x75, 0x01, 0x95, 0x06, 0xb1, 0x03,
    0xc0, 0xc0,

    /* Sideband output TLC used by bridge.py to submit touchpad frames. */
    0x06, 0x00, 0xff, 0x09, 0x01, 0xa1, 0x01,
    0x85, REPORT_ID_VENDOR_OUTPUT, 0x09, 0x01,
    0x15, 0x00, 0x26, 0xff, 0x00, 0x75, 0x08,
    0x95, DS5PTP_REPORT_SIZE - 1, 0x91, 0x02,
    0xc0,
};

/* Windows PTP certification blob from PeronGH/BLE-PTP-PoC (MIT). */
static const UCHAR G_PtpCertification[256] = {
    0xfc, 0x28, 0xfe, 0x84, 0x40, 0xcb, 0x9a, 0x87,
    0x0d, 0xbe, 0x57, 0x3c, 0xb6, 0x70, 0x09, 0x88,
    0x07, 0x97, 0x2d, 0x2b, 0xe3, 0x38, 0x34, 0xb6,
    0x6c, 0xed, 0xb0, 0xf7, 0xe5, 0x9c, 0xf6, 0xc2,
    0x2e, 0x84, 0x1b, 0xe8, 0xb4, 0x51, 0x78, 0x43,
    0x1f, 0x28, 0x4b, 0x7c, 0x2d, 0x53, 0xaf, 0xfc,
    0x47, 0x70, 0x1b, 0x59, 0x6f, 0x74, 0x43, 0xc4,
    0xf3, 0x47, 0x18, 0x53, 0x1a, 0xa2, 0xa1, 0x71,
    0xc7, 0x95, 0x0e, 0x31, 0x55, 0x21, 0xd3, 0xb5,
    0x1e, 0xe9, 0x0c, 0xba, 0xec, 0xb8, 0x89, 0x19,
    0x3e, 0xb3, 0xaf, 0x75, 0x81, 0x9d, 0x53, 0xb9,
    0x41, 0x57, 0xf4, 0x6d, 0x39, 0x25, 0x29, 0x7c,
    0x87, 0xd9, 0xb4, 0x98, 0x45, 0x7d, 0xa7, 0x26,
    0x9c, 0x65, 0x3b, 0x85, 0x68, 0x89, 0xd7, 0x3b,
    0xbd, 0xff, 0x14, 0x67, 0xf2, 0x2b, 0xf0, 0x2a,
    0x41, 0x54, 0xf0, 0xfd, 0x2c, 0x66, 0x7c, 0xf8,
    0xc0, 0x8f, 0x33, 0x13, 0x03, 0xf1, 0xd3, 0xc1,
    0x0b, 0x89, 0xd9, 0x1b, 0x62, 0xcd, 0x51, 0xb7,
    0x80, 0xb8, 0xaf, 0x3a, 0x10, 0xc1, 0x8a, 0x5b,
    0xe8, 0x8a, 0x56, 0xf0, 0x8c, 0xaa, 0xfa, 0x35,
    0xe9, 0x42, 0xc4, 0xd8, 0x55, 0xc3, 0x38, 0xcc,
    0x2b, 0x53, 0x5c, 0x69, 0x52, 0xd5, 0xc8, 0x73,
    0x02, 0x38, 0x7c, 0x73, 0xb6, 0x41, 0xe7, 0xff,
    0x05, 0xd8, 0x2b, 0x79, 0x9a, 0xe2, 0x34, 0x60,
    0x8f, 0xa3, 0x32, 0x1f, 0x09, 0x78, 0x62, 0xbc,
    0x80, 0xe3, 0x0f, 0xbd, 0x65, 0x20, 0x08, 0x13,
    0xc1, 0xe2, 0xee, 0x53, 0x2d, 0x86, 0x7e, 0xa7,
    0x5a, 0xc5, 0xd3, 0x7d, 0x98, 0xbe, 0x31, 0x48,
    0x1f, 0xfb, 0xda, 0xaf, 0xa2, 0xa8, 0x6a, 0x89,
    0xd6, 0xbf, 0xf2, 0xd3, 0x32, 0x2a, 0x9a, 0xe4,
    0xcf, 0x17, 0xb7, 0xb8, 0xf4, 0xe1, 0x33, 0x08,
    0x24, 0x8b, 0xc4, 0x43, 0xa5, 0xe5, 0x24, 0xc2,
};

HID_DESCRIPTOR G_DefaultHidDescriptor = {
    0x09, 0x21, 0x0100, 0x00, 0x01,
    {{0x22, sizeof(G_DefaultReportDescriptor)}}
};

static NTSTATUS CompletePendingRead(_In_ PDEVICE_CONTEXT DeviceContext);
static NTSTATUS QueueTouchReport(_In_ PDEVICE_CONTEXT DeviceContext,
                                 _In_reads_bytes_(DS5PTP_REPORT_SIZE) PUCHAR Buffer);

NTSTATUS
DriverEntry(
    _In_ PDRIVER_OBJECT DriverObject,
    _In_ PUNICODE_STRING RegistryPath
    )
{
    WDF_DRIVER_CONFIG config;
    WDF_DRIVER_CONFIG_INIT(&config, EvtDeviceAdd);
    return WdfDriverCreate(DriverObject, RegistryPath, WDF_NO_OBJECT_ATTRIBUTES,
                           &config, WDF_NO_HANDLE);
}

NTSTATUS
EvtDeviceAdd(
    _In_ WDFDRIVER Driver,
    _Inout_ PWDFDEVICE_INIT DeviceInit
    )
{
    NTSTATUS status;
    WDF_OBJECT_ATTRIBUTES attributes;
    WDFDEVICE device;
    PDEVICE_CONTEXT context;
    UNREFERENCED_PARAMETER(Driver);

    WdfFdoInitSetFilter(DeviceInit);
    WDF_OBJECT_ATTRIBUTES_INIT_CONTEXT_TYPE(&attributes, DEVICE_CONTEXT);
    status = WdfDeviceCreate(&DeviceInit, &attributes, &device);
    if (!NT_SUCCESS(status)) {
        return status;
    }

    context = GetDeviceContext(device);
    RtlZeroMemory(context, sizeof(*context));
    context->Device = device;
    context->HidDescriptor = G_DefaultHidDescriptor;
    context->ReportDescriptor = G_DefaultReportDescriptor;
    context->InputMode = 3;
    context->FunctionSwitches = 3;
    context->HidDeviceAttributes.Size = sizeof(HID_DEVICE_ATTRIBUTES);
    context->HidDeviceAttributes.VendorID = DS5PTP_VENDOR_ID;
    context->HidDeviceAttributes.ProductID = DS5PTP_PRODUCT_ID;
    context->HidDeviceAttributes.VersionNumber = DS5PTP_VERSION;

    status = WdfWaitLockCreate(WDF_NO_OBJECT_ATTRIBUTES, &context->ReportLock);
    if (!NT_SUCCESS(status)) {
        return status;
    }
    status = QueueCreate(device, &context->DefaultQueue);
    if (!NT_SUCCESS(status)) {
        return status;
    }
    return ManualQueueCreate(device, &context->ManualQueue);
}

#ifdef _KERNEL_MODE
EVT_WDF_IO_QUEUE_IO_INTERNAL_DEVICE_CONTROL EvtIoDeviceControl;
#else
EVT_WDF_IO_QUEUE_IO_DEVICE_CONTROL EvtIoDeviceControl;
#endif

NTSTATUS
QueueCreate(_In_ WDFDEVICE Device, _Out_ WDFQUEUE *Queue)
{
    NTSTATUS status;
    WDF_IO_QUEUE_CONFIG config;
    WDF_OBJECT_ATTRIBUTES attributes;
    PQUEUE_CONTEXT context;

    WDF_IO_QUEUE_CONFIG_INIT_DEFAULT_QUEUE(&config, WdfIoQueueDispatchParallel);
#ifdef _KERNEL_MODE
    config.EvtIoInternalDeviceControl = EvtIoDeviceControl;
#else
    config.EvtIoDeviceControl = EvtIoDeviceControl;
#endif
    WDF_OBJECT_ATTRIBUTES_INIT_CONTEXT_TYPE(&attributes, QUEUE_CONTEXT);
    status = WdfIoQueueCreate(Device, &config, &attributes, Queue);
    if (!NT_SUCCESS(status)) {
        return status;
    }
    context = GetQueueContext(*Queue);
    context->Queue = *Queue;
    context->DeviceContext = GetDeviceContext(Device);
    return STATUS_SUCCESS;
}

VOID
EvtIoDeviceControl(
    _In_ WDFQUEUE Queue,
    _In_ WDFREQUEST Request,
    _In_ size_t OutputBufferLength,
    _In_ size_t InputBufferLength,
    _In_ ULONG IoControlCode
    )
{
    NTSTATUS status;
    BOOLEAN complete = TRUE;
    PQUEUE_CONTEXT queueContext = GetQueueContext(Queue);
    PDEVICE_CONTEXT deviceContext = queueContext->DeviceContext;
    UNREFERENCED_PARAMETER(OutputBufferLength);
    UNREFERENCED_PARAMETER(InputBufferLength);

    switch (IoControlCode) {
    case IOCTL_HID_GET_DEVICE_DESCRIPTOR:
        status = RequestCopyFromBuffer(Request, &deviceContext->HidDescriptor,
                                       deviceContext->HidDescriptor.bLength);
        break;
    case IOCTL_HID_GET_DEVICE_ATTRIBUTES:
        status = RequestCopyFromBuffer(Request, &deviceContext->HidDeviceAttributes,
                                       sizeof(HID_DEVICE_ATTRIBUTES));
        break;
    case IOCTL_HID_GET_REPORT_DESCRIPTOR:
        status = RequestCopyFromBuffer(Request, deviceContext->ReportDescriptor,
                                       deviceContext->HidDescriptor.DescriptorList[0].wReportLength);
        break;
    case IOCTL_HID_READ_REPORT:
        status = ReadReport(queueContext, Request, &complete);
        break;
    case IOCTL_HID_WRITE_REPORT:
        status = WriteReport(queueContext, Request);
        break;
#ifndef _KERNEL_MODE
    case IOCTL_UMDF_HID_GET_FEATURE:
        status = GetFeature(queueContext, Request);
        break;
    case IOCTL_UMDF_HID_SET_FEATURE:
        status = SetFeature(queueContext, Request);
        break;
    case IOCTL_UMDF_HID_GET_INPUT_REPORT:
        status = GetInputReport(queueContext, Request);
        break;
    case IOCTL_UMDF_HID_SET_OUTPUT_REPORT:
        status = SetOutputReport(queueContext, Request);
        break;
#endif
    case IOCTL_HID_GET_STRING:
        status = GetString(Request);
        break;
    case IOCTL_HID_GET_INDEXED_STRING:
        status = GetIndexedString(Request);
        break;
    default:
        status = STATUS_NOT_IMPLEMENTED;
        break;
    }

    if (complete) {
        WdfRequestComplete(Request, status);
    }
}

NTSTATUS
RequestCopyFromBuffer(
    _In_ WDFREQUEST Request,
    _In_ PVOID SourceBuffer,
    _In_ size_t NumBytesToCopyFrom
    )
{
    NTSTATUS status;
    WDFMEMORY memory;
    size_t outputLength;

    status = WdfRequestRetrieveOutputMemory(Request, &memory);
    if (!NT_SUCCESS(status)) {
        return status;
    }
    WdfMemoryGetBuffer(memory, &outputLength);
    if (outputLength < NumBytesToCopyFrom) {
        return STATUS_INVALID_BUFFER_SIZE;
    }
    status = WdfMemoryCopyFromBuffer(memory, 0, SourceBuffer, NumBytesToCopyFrom);
    if (NT_SUCCESS(status)) {
        WdfRequestSetInformation(Request, NumBytesToCopyFrom);
    }
    return status;
}

NTSTATUS
ManualQueueCreate(_In_ WDFDEVICE Device, _Out_ WDFQUEUE *Queue)
{
    WDF_IO_QUEUE_CONFIG config;
    WDF_IO_QUEUE_CONFIG_INIT(&config, WdfIoQueueDispatchManual);
    return WdfIoQueueCreate(Device, &config, WDF_NO_OBJECT_ATTRIBUTES, Queue);
}

static NTSTATUS
CompletePendingRead(_In_ PDEVICE_CONTEXT DeviceContext)
{
    NTSTATUS status;
    WDFREQUEST request;
    DS5PTP_INPUT_REPORT report;

    WdfWaitLockAcquire(DeviceContext->ReportLock, NULL);
    if (!DeviceContext->ReportReady) {
        WdfWaitLockRelease(DeviceContext->ReportLock);
        return STATUS_NO_MORE_ENTRIES;
    }
    status = WdfIoQueueRetrieveNextRequest(DeviceContext->ManualQueue, &request);
    if (!NT_SUCCESS(status)) {
        WdfWaitLockRelease(DeviceContext->ReportLock);
        return status;
    }
    report = DeviceContext->PendingReport;
    DeviceContext->ReportReady = FALSE;
    WdfWaitLockRelease(DeviceContext->ReportLock);

    status = RequestCopyFromBuffer(request, &report, sizeof(report));
    WdfRequestComplete(request, status);
    return status;
}

static NTSTATUS
QueueTouchReport(
    _In_ PDEVICE_CONTEXT DeviceContext,
    _In_reads_bytes_(DS5PTP_REPORT_SIZE) PUCHAR Buffer
    )
{
    WdfWaitLockAcquire(DeviceContext->ReportLock, NULL);
    DeviceContext->PendingReport.ReportId = REPORT_ID_TOUCHPAD;
    RtlCopyMemory(((PUCHAR)&DeviceContext->PendingReport) + 1,
                  Buffer + 1, DS5PTP_REPORT_SIZE - 1);
    DeviceContext->PendingReport.ContactCount &= 0x7f;
    if (DeviceContext->PendingReport.ContactCount > DS5PTP_CONTACT_COUNT) {
        DeviceContext->PendingReport.ContactCount = DS5PTP_CONTACT_COUNT;
    }
    DeviceContext->ReportReady = TRUE;
    WdfWaitLockRelease(DeviceContext->ReportLock);
    CompletePendingRead(DeviceContext);
    return STATUS_SUCCESS;
}

NTSTATUS
ReadReport(
    _In_ PQUEUE_CONTEXT QueueContext,
    _In_ WDFREQUEST Request,
    _Always_(_Out_) BOOLEAN *CompleteRequest
    )
{
    NTSTATUS status;
    DS5PTP_INPUT_REPORT report;
    PDEVICE_CONTEXT context = QueueContext->DeviceContext;

    WdfWaitLockAcquire(context->ReportLock, NULL);
    if (context->ReportReady) {
        report = context->PendingReport;
        context->ReportReady = FALSE;
        WdfWaitLockRelease(context->ReportLock);
        *CompleteRequest = TRUE;
        return RequestCopyFromBuffer(Request, &report, sizeof(report));
    }
    WdfWaitLockRelease(context->ReportLock);

    status = WdfRequestForwardToIoQueue(Request, context->ManualQueue);
    if (!NT_SUCCESS(status)) {
        *CompleteRequest = TRUE;
        return status;
    }
    *CompleteRequest = FALSE;
    CompletePendingRead(context);
    return STATUS_SUCCESS;
}

NTSTATUS
WriteReport(_In_ PQUEUE_CONTEXT QueueContext, _In_ WDFREQUEST Request)
{
    NTSTATUS status;
    HID_XFER_PACKET packet;

    status = RequestGetHidXferPacket_ToWriteToDevice(Request, &packet);
    if (!NT_SUCCESS(status)) {
        return status;
    }
    if (packet.reportId != REPORT_ID_VENDOR_OUTPUT ||
        packet.reportBufferLen < DS5PTP_VENDOR_OUTPUT_SIZE) {
        return STATUS_INVALID_BUFFER_SIZE;
    }
    status = QueueTouchReport(QueueContext->DeviceContext, packet.reportBuffer);
    if (NT_SUCCESS(status)) {
        WdfRequestSetInformation(Request, DS5PTP_VENDOR_OUTPUT_SIZE);
    }
    return status;
}

NTSTATUS
GetFeature(_In_ PQUEUE_CONTEXT QueueContext, _In_ WDFREQUEST Request)
{
    NTSTATUS status;
    HID_XFER_PACKET packet;
    ULONG reportSize;
    PDEVICE_CONTEXT context = QueueContext->DeviceContext;

    status = RequestGetHidXferPacket_ToReadFromDevice(Request, &packet);
    if (!NT_SUCCESS(status)) {
        return status;
    }

    switch (packet.reportId) {
    case REPORT_ID_MAX_COUNT:
        reportSize = 3;
        if (packet.reportBufferLen < reportSize) return STATUS_INVALID_BUFFER_SIZE;
        packet.reportBuffer[0] = REPORT_ID_MAX_COUNT;
        packet.reportBuffer[1] = DS5PTP_CONTACT_COUNT;
        packet.reportBuffer[2] = 0;
        break;
    case REPORT_ID_INPUT_MODE:
        reportSize = 2;
        if (packet.reportBufferLen < reportSize) return STATUS_INVALID_BUFFER_SIZE;
        packet.reportBuffer[0] = REPORT_ID_INPUT_MODE;
        packet.reportBuffer[1] = context->InputMode;
        break;
    case REPORT_ID_FUNCTION_SWITCH:
        reportSize = 2;
        if (packet.reportBufferLen < reportSize) return STATUS_INVALID_BUFFER_SIZE;
        packet.reportBuffer[0] = REPORT_ID_FUNCTION_SWITCH;
        packet.reportBuffer[1] = context->FunctionSwitches;
        break;
    case REPORT_ID_CERTIFICATION:
        reportSize = DS5PTP_CERTIFICATION_SIZE;
        if (packet.reportBufferLen < reportSize) return STATUS_INVALID_BUFFER_SIZE;
        packet.reportBuffer[0] = REPORT_ID_CERTIFICATION;
        RtlCopyMemory(packet.reportBuffer + 1, G_PtpCertification,
                      sizeof(G_PtpCertification));
        break;
    default:
        return STATUS_INVALID_PARAMETER;
    }
    WdfRequestSetInformation(Request, reportSize);
    return STATUS_SUCCESS;
}

NTSTATUS
SetFeature(_In_ PQUEUE_CONTEXT QueueContext, _In_ WDFREQUEST Request)
{
    NTSTATUS status;
    HID_XFER_PACKET packet;
    PDEVICE_CONTEXT context = QueueContext->DeviceContext;

    status = RequestGetHidXferPacket_ToWriteToDevice(Request, &packet);
    if (!NT_SUCCESS(status)) {
        return status;
    }
    if (packet.reportBufferLen < 2) {
        return STATUS_INVALID_BUFFER_SIZE;
    }
    if (packet.reportId == REPORT_ID_INPUT_MODE) {
        context->InputMode = packet.reportBuffer[1];
    } else if (packet.reportId == REPORT_ID_FUNCTION_SWITCH) {
        context->FunctionSwitches = packet.reportBuffer[1] & 0x03;
    } else if (packet.reportId != REPORT_ID_CERTIFICATION) {
        return STATUS_INVALID_PARAMETER;
    }
    WdfRequestSetInformation(Request, packet.reportBufferLen);
    return STATUS_SUCCESS;
}

NTSTATUS
GetInputReport(_In_ PQUEUE_CONTEXT QueueContext, _In_ WDFREQUEST Request)
{
    HID_XFER_PACKET packet;
    NTSTATUS status = RequestGetHidXferPacket_ToReadFromDevice(Request, &packet);
    if (!NT_SUCCESS(status)) {
        return status;
    }
    if (packet.reportId != REPORT_ID_TOUCHPAD) {
        return STATUS_INVALID_PARAMETER;
    }
    return RequestCopyFromBuffer(Request, &QueueContext->DeviceContext->PendingReport,
                                 sizeof(DS5PTP_INPUT_REPORT));
}

NTSTATUS
SetOutputReport(_In_ PQUEUE_CONTEXT QueueContext, _In_ WDFREQUEST Request)
{
    return WriteReport(QueueContext, Request);
}

NTSTATUS
GetStringId(
    _In_ WDFREQUEST Request,
    _Out_ ULONG *StringId,
    _Out_ ULONG *LanguageId
    )
{
    NTSTATUS status;
    WDFMEMORY memory;
    size_t length;
    PULONG value;

    status = WdfRequestRetrieveInputMemory(Request, &memory);
    if (!NT_SUCCESS(status)) {
        return status;
    }
    value = (PULONG)WdfMemoryGetBuffer(memory, &length);
    if (length < sizeof(ULONG)) {
        return STATUS_INVALID_BUFFER_SIZE;
    }
    *StringId = *value & 0xffff;
    *LanguageId = *value >> 16;
    return STATUS_SUCCESS;
}

NTSTATUS
GetIndexedString(_In_ WDFREQUEST Request)
{
    ULONG index;
    ULONG language;
    NTSTATUS status = GetStringId(Request, &index, &language);
    UNREFERENCED_PARAMETER(language);
    if (!NT_SUCCESS(status)) return status;
    if (index != DS5PTP_DEVICE_STRING_INDEX) return STATUS_INVALID_PARAMETER;
    return RequestCopyFromBuffer(Request, DS5PTP_DEVICE_STRING,
                                 sizeof(DS5PTP_DEVICE_STRING));
}

NTSTATUS
GetString(_In_ WDFREQUEST Request)
{
    ULONG id;
    ULONG language;
    PWSTR value;
    size_t size;
    NTSTATUS status = GetStringId(Request, &id, &language);
    UNREFERENCED_PARAMETER(language);
    if (!NT_SUCCESS(status)) return status;

    switch (id) {
    case HID_STRING_ID_IMANUFACTURER:
        value = DS5PTP_MANUFACTURER_STRING;
        size = sizeof(DS5PTP_MANUFACTURER_STRING);
        break;
    case HID_STRING_ID_IPRODUCT:
        value = DS5PTP_PRODUCT_STRING;
        size = sizeof(DS5PTP_PRODUCT_STRING);
        break;
    case HID_STRING_ID_ISERIALNUMBER:
        value = DS5PTP_SERIAL_NUMBER_STRING;
        size = sizeof(DS5PTP_SERIAL_NUMBER_STRING);
        break;
    default:
        return STATUS_INVALID_PARAMETER;
    }
    return RequestCopyFromBuffer(Request, value, size);
}
