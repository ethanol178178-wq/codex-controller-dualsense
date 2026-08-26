/*
 * DS5 Vibe Hub virtual Precision Touchpad.
 *
 * The UMDF HID plumbing is derived from Microsoft's vhidmini2 sample.
 */
#pragma once

#include <windows.h>
#include <wdf.h>
#include <hidport.h>

typedef UCHAR HID_REPORT_DESCRIPTOR, *PHID_REPORT_DESCRIPTOR;

#define DS5PTP_VENDOR_ID                 0x1209
#define DS5PTP_PRODUCT_ID                0xD505
#define DS5PTP_VERSION                   0x0100

#define REPORT_ID_INPUT_MODE             0x04
#define REPORT_ID_TOUCHPAD               0x05
#define REPORT_ID_FUNCTION_SWITCH        0x06
#define REPORT_ID_MAX_COUNT              0x07
#define REPORT_ID_CERTIFICATION          0x08
#define REPORT_ID_VENDOR_OUTPUT          0x09

#define DS5PTP_CONTACT_COUNT             5
#define DS5PTP_REPORT_SIZE               50
#define DS5PTP_VENDOR_OUTPUT_SIZE        50
#define DS5PTP_CERTIFICATION_SIZE        257

#define DS5PTP_MANUFACTURER_STRING       L"DS5 Vibe Hub"
#define DS5PTP_PRODUCT_STRING            L"DS5 Virtual Precision Touchpad"
#define DS5PTP_SERIAL_NUMBER_STRING      L"DS5VIBE-PTP"
#define DS5PTP_DEVICE_STRING             L"DS5 Virtual Precision Touchpad"
#define DS5PTP_DEVICE_STRING_INDEX       5

#include <pshpack1.h>

typedef struct _DS5PTP_CONTACT {
    UCHAR Status;
    ULONG ContactId;
    USHORT X;
    USHORT Y;
} DS5PTP_CONTACT, *PDS5PTP_CONTACT;

typedef struct _DS5PTP_INPUT_REPORT {
    UCHAR ReportId;
    DS5PTP_CONTACT Contacts[DS5PTP_CONTACT_COUNT];
    USHORT ScanTime;
    UCHAR ContactCount;
    UCHAR Buttons;
} DS5PTP_INPUT_REPORT, *PDS5PTP_INPUT_REPORT;

typedef struct _DS5PTP_VENDOR_REPORT {
    UCHAR ReportId;
    UCHAR Payload[DS5PTP_REPORT_SIZE - 1];
} DS5PTP_VENDOR_REPORT, *PDS5PTP_VENDOR_REPORT;

#include <poppack.h>

C_ASSERT(sizeof(DS5PTP_INPUT_REPORT) == DS5PTP_REPORT_SIZE);
C_ASSERT(sizeof(DS5PTP_VENDOR_REPORT) == DS5PTP_VENDOR_OUTPUT_SIZE);

DRIVER_INITIALIZE DriverEntry;
EVT_WDF_DRIVER_DEVICE_ADD EvtDeviceAdd;

typedef struct _DEVICE_CONTEXT {
    WDFDEVICE Device;
    WDFQUEUE DefaultQueue;
    WDFQUEUE ManualQueue;
    WDFWAITLOCK ReportLock;
    HID_DEVICE_ATTRIBUTES HidDeviceAttributes;
    HID_DESCRIPTOR HidDescriptor;
    PHID_REPORT_DESCRIPTOR ReportDescriptor;
    DS5PTP_INPUT_REPORT PendingReport;
    BOOLEAN ReportReady;
    UCHAR InputMode;
    UCHAR FunctionSwitches;
} DEVICE_CONTEXT, *PDEVICE_CONTEXT;

WDF_DECLARE_CONTEXT_TYPE_WITH_NAME(DEVICE_CONTEXT, GetDeviceContext);

typedef struct _QUEUE_CONTEXT {
    WDFQUEUE Queue;
    PDEVICE_CONTEXT DeviceContext;
} QUEUE_CONTEXT, *PQUEUE_CONTEXT;

WDF_DECLARE_CONTEXT_TYPE_WITH_NAME(QUEUE_CONTEXT, GetQueueContext);

NTSTATUS QueueCreate(_In_ WDFDEVICE Device, _Out_ WDFQUEUE *Queue);
NTSTATUS ManualQueueCreate(_In_ WDFDEVICE Device, _Out_ WDFQUEUE *Queue);
NTSTATUS ReadReport(_In_ PQUEUE_CONTEXT QueueContext, _In_ WDFREQUEST Request,
                    _Always_(_Out_) BOOLEAN *CompleteRequest);
NTSTATUS WriteReport(_In_ PQUEUE_CONTEXT QueueContext, _In_ WDFREQUEST Request);
NTSTATUS GetFeature(_In_ PQUEUE_CONTEXT QueueContext, _In_ WDFREQUEST Request);
NTSTATUS SetFeature(_In_ PQUEUE_CONTEXT QueueContext, _In_ WDFREQUEST Request);
NTSTATUS GetInputReport(_In_ PQUEUE_CONTEXT QueueContext, _In_ WDFREQUEST Request);
NTSTATUS SetOutputReport(_In_ PQUEUE_CONTEXT QueueContext, _In_ WDFREQUEST Request);
NTSTATUS GetString(_In_ WDFREQUEST Request);
NTSTATUS GetIndexedString(_In_ WDFREQUEST Request);
NTSTATUS GetStringId(_In_ WDFREQUEST Request, _Out_ ULONG *StringId,
                     _Out_ ULONG *LanguageId);
NTSTATUS RequestCopyFromBuffer(_In_ WDFREQUEST Request, _In_ PVOID SourceBuffer,
                               _In_ size_t NumBytesToCopyFrom);
NTSTATUS RequestGetHidXferPacket_ToReadFromDevice(_In_ WDFREQUEST Request,
                                                   _Out_ HID_XFER_PACKET *Packet);
NTSTATUS RequestGetHidXferPacket_ToWriteToDevice(_In_ WDFREQUEST Request,
                                                  _Out_ HID_XFER_PACKET *Packet);
