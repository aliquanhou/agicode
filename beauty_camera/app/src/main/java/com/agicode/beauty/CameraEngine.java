package com.agicode.beauty;

import android.Manifest;
import android.content.Context;
import android.content.pm.PackageManager;
import android.graphics.ImageFormat;
import android.graphics.Rect;
import android.graphics.SurfaceTexture;
import android.hardware.camera2.CameraAccessException;
import android.hardware.camera2.CameraCaptureSession;
import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CameraDevice;
import android.hardware.camera2.CameraManager;
import android.hardware.camera2.CaptureRequest;
import android.hardware.camera2.CaptureResult;
import android.hardware.camera2.TotalCaptureResult;
import android.hardware.camera2.params.MeteringRectangle;
import android.hardware.camera2.params.StreamConfigurationMap;
import android.media.Image;
import android.media.ImageReader;
import android.os.Build;
import android.os.Handler;
import android.os.HandlerThread;
import android.util.Log;
import android.util.Range;
import android.util.Size;
import android.view.Surface;

import java.nio.ByteBuffer;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;

/**
 * 专业相机引擎 v3.0
 * 参考 OpenCamera 设计
 * 支持：手动对焦/曝光/ISO/快门/白平衡/峰值对焦/直方图/HDR/连拍
 */
public class CameraEngine {

    private static final String TAG = "CameraEngine";

    private Context context;
    private CameraManager cameraManager;
    private CameraDevice cameraDevice;
    private CameraCaptureSession captureSession;
    private CaptureRequest.Builder previewBuilder;
    private CaptureRequest.Builder photoBuilder;

    private String cameraId;
    private Size previewSize;
    private Size photoSize;
    private int cameraFacing = CameraCharacteristics.LENS_FACING_BACK;

    private HandlerThread backgroundThread;
    private Handler backgroundHandler;

    private ImageReader imageReader;
    private OnPhotoTakenListener photoListener;

    // 变焦
    private float zoomRatio = 1.0f;
    private float maxZoom = 10.0f;
    private Rect zoomRect;

    // 曝光
    private int exposureCompensation = 0;
    private Range<Integer> exposureRange;

    // 闪光灯
    private int flashMode = CaptureRequest.FLASH_MODE_OFF;

    // 专业模式参数
    private boolean proMode = false;
    private int manualISO = 100;
    private Range<Integer> isoRange;
    private long manualShutterSpeed = 10000000L;
    private Range<Long> shutterSpeedRange;
    private int manualWhiteBalance = 5000;
    private float manualFocusDistance = 0f;
    private boolean manualFocusEnabled = false;

    // 场景模式
    private String sceneMode = "auto";

    // 对焦
    private MeteringRectangle[] afRegions = new MeteringRectangle[0];
    private MeteringRectangle[] aeRegions = new MeteringRectangle[0];

    // 回调
    private OnCameraReadyListener readyListener;
    private OnFocusListener focusListener;
    private OnHistogramDataListener histogramListener;

    // 直方图
    private int[] histogramData = new int[256];
    private boolean histogramEnabled = false;

    // 连拍
    private boolean burstMode = false;
    private int burstCount = 0;
    private int burstMax = 10;
    private OnBurstPhotoListener burstListener;

    // 预览 Surface
    private Surface previewSurface;

    // ========== 接口 ==========
    public interface OnPhotoTakenListener {
        void onPhotoTaken(byte[] data, int width, int height);
    }

    public interface OnCameraReadyListener {
        void onCameraReady();
        void onCameraError(String error);
    }

    public interface OnFocusListener {
        void onFocusStarted();
        void onFocusSuccess(boolean success);
    }

    public interface OnHistogramDataListener {
        void onHistogramData(int[] histogram);
    }

    public interface OnBurstPhotoListener {
        void onBurstProgress(int current, int total);
        void onBurstComplete(int totalPhotos);
    }

    public CameraEngine(Context context) {
        this.context = context;
        this.cameraManager = (CameraManager) context.getSystemService(Context.CAMERA_SERVICE);
    }

    public void start() {
        startBackgroundThread();
        try {
            String[] ids = cameraManager.getCameraIdList();
            if (ids.length == 0) {
                Log.e(TAG, "没有找到摄像头");
                return;
            }
            for (String id : ids) {
                CameraCharacteristics chars = cameraManager.getCameraCharacteristics(id);
                Integer facing = chars.get(CameraCharacteristics.LENS_FACING);
                if (facing != null && facing == cameraFacing) {
                    cameraId = id;
                    break;
                }
            }
            if (cameraId == null) cameraId = ids[0];
            initCameraParams(cameraId);
            openCamera();
        } catch (CameraAccessException e) {
            Log.e(TAG, "相机访问失败", e);
        }
    }

    private void initCameraParams(String id) throws CameraAccessException {
        CameraCharacteristics chars = cameraManager.getCameraCharacteristics(id);
        StreamConfigurationMap map = chars.get(CameraCharacteristics.SCALER_STREAM_CONFIGURATION_MAP);
        if (map != null) {
            Size[] sizes = map.getOutputSizes(SurfaceTexture.class);
            previewSize = chooseOptimalSize(sizes, 1920, 1080);
            if (previewSize == null) previewSize = new Size(1920, 1080);
            photoSize = chooseOptimalSize(map.getOutputSizes(ImageFormat.JPEG), 4000, 3000);
            if (photoSize == null) photoSize = new Size(4000, 3000);
        }

        Float maxZoomFloat = chars.get(CameraCharacteristics.SCALER_AVAILABLE_MAX_DIGITAL_ZOOM);
        if (maxZoomFloat != null) maxZoom = maxZoomFloat;
        Rect activeRect = chars.get(CameraCharacteristics.SENSOR_INFO_ACTIVE_ARRAY_SIZE);
        if (activeRect != null) zoomRect = activeRect;

        exposureRange = chars.get(CameraCharacteristics.CONTROL_AE_COMPENSATION_RANGE);
        if (exposureRange == null) exposureRange = new Range<>(-4, 4);

        isoRange = chars.get(CameraCharacteristics.SENSOR_INFO_SENSITIVITY_RANGE);
        if (isoRange == null) isoRange = new Range<>(100, 3200);

        shutterSpeedRange = chars.get(CameraCharacteristics.SENSOR_INFO_EXPOSURE_TIME_RANGE);
        if (shutterSpeedRange == null) shutterSpeedRange = new Range<>(1000000L, 30000000L);
    }

    private void openCamera() throws CameraAccessException {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            if (context.checkSelfPermission(Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
                Log.e(TAG, "没有相机权限");
                return;
            }
        }
        cameraManager.openCamera(cameraId, new CameraDevice.StateCallback() {
            @Override
            public void onOpened(CameraDevice device) {
                cameraDevice = device;
                createPreviewSession();
                if (readyListener != null) readyListener.onCameraReady();
            }

            @Override
            public void onDisconnected(CameraDevice device) {
                device.close();
                cameraDevice = null;
            }

            @Override
            public void onError(CameraDevice device, int error) {
                device.close();
                cameraDevice = null;
                if (readyListener != null) readyListener.onCameraError("Camera error: " + error);
            }
        }, backgroundHandler);
    }

    private void createPreviewSession() {
        if (cameraDevice == null) return;
        try {
            previewBuilder = cameraDevice.createCaptureRequest(CameraDevice.TEMPLATE_PREVIEW);
            photoBuilder = cameraDevice.createCaptureRequest(CameraDevice.TEMPLATE_STILL_CAPTURE);

            imageReader = ImageReader.newInstance(photoSize.getWidth(), photoSize.getHeight(), ImageFormat.JPEG, 5);
            imageReader.setOnImageAvailableListener(reader -> {
                try (Image image = reader.acquireLatestImage()) {
                    if (image != null && photoListener != null) {
                        ByteBuffer buffer = image.getPlanes()[0].getBuffer();
                        byte[] data = new byte[buffer.remaining()];
                        buffer.get(data);
                        photoListener.onPhotoTaken(data, image.getWidth(), image.getHeight());
                    }
                } catch (Exception e) {
                    Log.e(TAG, "拍照回调错误", e);
                }
            }, backgroundHandler);

            List<Surface> surfaces = new ArrayList<>();
            surfaces.add(imageReader.getSurface());
            if (previewSurface != null) {
                surfaces.add(previewSurface);
            }

            cameraDevice.createCaptureSession(surfaces,
                new CameraCaptureSession.StateCallback() {
                    @Override
                    public void onConfigured(CameraCaptureSession session) {
                        captureSession = session;
                        applyPreviewSettings();
                    }

                    @Override
                    public void onConfigureFailed(CameraCaptureSession session) {
                        Log.e(TAG, "配置预览会话失败");
                    }
                }, backgroundHandler);

        } catch (CameraAccessException e) {
            Log.e(TAG, "创建预览会话失败", e);
        }
    }

    public void setPreviewSurface(Surface surface) {
        this.previewSurface = surface;
    }

    public void setPreviewTexture(SurfaceTexture texture) {
        if (texture != null) {
            if (previewSize == null) {
                previewSize = new Size(1920, 1080);
            }
            texture.setDefaultBufferSize(previewSize.getWidth(), previewSize.getHeight());
            setPreviewSurface(new Surface(texture));
        }
    }

    private void applyPreviewSettings() {
        if (captureSession == null || previewBuilder == null) return;
        try {
            applyZoom();
            applyFlash();
            applyFocusMode();
            applyExposure();
            applyProSettings();

            captureSession.setRepeatingRequest(previewBuilder.build(), new CameraCaptureSession.CaptureCallback() {
                @Override
                public void onCaptureCompleted(CameraCaptureSession session, CaptureRequest request, TotalCaptureResult result) {
                    super.onCaptureCompleted(session, request, result);
                    if (histogramEnabled && histogramListener != null) {
                        histogramListener.onHistogramData(histogramData);
                    }
                }
            }, backgroundHandler);

        } catch (CameraAccessException e) {
            Log.e(TAG, "应用预览设置失败", e);
        }
    }

    public void setZoom(float ratio) {
        this.zoomRatio = Math.max(1.0f, Math.min(ratio, maxZoom));
        applyZoom();
    }

    public float getZoom() { return zoomRatio; }
    public float getMaxZoom() { return maxZoom; }

    private void applyZoom() {
        if (previewBuilder == null || zoomRect == null) return;
        Rect newRect = new Rect(
            (int)(zoomRect.width() / 2 / zoomRatio),
            (int)(zoomRect.height() / 2 / zoomRatio),
            (int)(zoomRect.width() - zoomRect.width() / 2 / zoomRatio),
            (int)(zoomRect.height() - zoomRect.height() / 2 / zoomRatio)
        );
        previewBuilder.set(CaptureRequest.SCALER_CROP_REGION, newRect);
        if (photoBuilder != null) {
            photoBuilder.set(CaptureRequest.SCALER_CROP_REGION, newRect);
        }
    }

    public void setFlashMode(int mode) {
        this.flashMode = mode;
        applyFlash();
    }

    public int getFlashMode() { return flashMode; }

    private void applyFlash() {
        if (previewBuilder == null) return;
        previewBuilder.set(CaptureRequest.FLASH_MODE, flashMode);
        if (photoBuilder != null) {
            photoBuilder.set(CaptureRequest.FLASH_MODE, flashMode);
        }
    }

    public void triggerFocus(float x, float y, int viewWidth, int viewHeight) {
        if (captureSession == null || previewBuilder == null) return;
        try {
            Rect sensorRect = zoomRect != null ? zoomRect : new Rect(0, 0, 100, 100);
            int sensorX = (int)((x / viewWidth) * sensorRect.width()) + sensorRect.left;
            int sensorY = (int)((y / viewHeight) * sensorRect.height()) + sensorRect.top;
            int halfSize = Math.min(sensorRect.width(), sensorRect.height()) / 8;

            MeteringRectangle region = new MeteringRectangle(
                Math.max(sensorX - halfSize, sensorRect.left),
                Math.max(sensorY - halfSize, sensorRect.top),
                halfSize * 2, halfSize * 2,
                MeteringRectangle.METERING_WEIGHT_MAX
            );

            afRegions = new MeteringRectangle[]{region};
            aeRegions = new MeteringRectangle[]{region};

            previewBuilder.set(CaptureRequest.CONTROL_AF_REGIONS, afRegions);
            previewBuilder.set(CaptureRequest.CONTROL_AE_REGIONS, aeRegions);
            previewBuilder.set(CaptureRequest.CONTROL_AF_MODE, CaptureRequest.CONTROL_AF_MODE_AUTO);
            previewBuilder.set(CaptureRequest.CONTROL_AE_PRECAPTURE_TRIGGER, CaptureRequest.CONTROL_AE_PRECAPTURE_TRIGGER_START);

            captureSession.capture(previewBuilder.build(), new CameraCaptureSession.CaptureCallback() {
                @Override
                public void onCaptureCompleted(CameraCaptureSession session, CaptureRequest request, TotalCaptureResult result) {
                    Integer afState = result.get(CaptureResult.CONTROL_AF_STATE);
                    if (afState != null) {
                        boolean success = afState == CaptureResult.CONTROL_AF_STATE_FOCUSED_LOCKED
                            || afState == CaptureResult.CONTROL_AF_STATE_PASSIVE_FOCUSED;
                        if (focusListener != null) focusListener.onFocusSuccess(success);
                    }
                }
            }, backgroundHandler);

            if (focusListener != null) focusListener.onFocusStarted();

        } catch (CameraAccessException e) {
            Log.e(TAG, "触发对焦失败", e);
        }
    }

    private void applyFocusMode() {
        if (previewBuilder == null) return;
        if (manualFocusEnabled) {
            previewBuilder.set(CaptureRequest.CONTROL_AF_MODE, CaptureRequest.CONTROL_AF_MODE_OFF);
            previewBuilder.set(CaptureRequest.LENS_FOCUS_DISTANCE, manualFocusDistance);
        } else {
            previewBuilder.set(CaptureRequest.CONTROL_AF_MODE, CaptureRequest.CONTROL_AF_MODE_CONTINUOUS_PICTURE);
        }
    }

    public void setProMode(boolean enabled) {
        this.proMode = enabled;
        applyProSettings();
    }

    public boolean isProMode() { return proMode; }

    public void setManualISO(int iso) {
        this.manualISO = Math.max(isoRange.getLower(), Math.min(iso, isoRange.getUpper()));
        applyProSettings();
    }

    public int getManualISO() { return manualISO; }
    public Range<Integer> getISORange() { return isoRange; }

    public void setManualShutterSpeed(long ns) {
        this.manualShutterSpeed = Math.max(shutterSpeedRange.getLower(), Math.min(ns, shutterSpeedRange.getUpper()));
        applyProSettings();
    }

    public long getManualShutterSpeed() { return manualShutterSpeed; }
    public Range<Long> getShutterSpeedRange() { return shutterSpeedRange; }

    public void setManualWhiteBalance(int kelvin) {
        this.manualWhiteBalance = Math.max(2000, Math.min(kelvin, 8000));
        applyProSettings();
    }

    public int getManualWhiteBalance() { return manualWhiteBalance; }

    public void setManualFocusDistance(float dist) {
        this.manualFocusDistance = Math.max(0f, Math.min(dist, 1f));
        this.manualFocusEnabled = true;
        applyFocusMode();
    }

    public float getManualFocusDistance() { return manualFocusDistance; }

    public void setExposureCompensation(int ev) {
        this.exposureCompensation = Math.max(exposureRange.getLower(), Math.min(ev, exposureRange.getUpper()));
        applyExposure();
    }

    public int getExposureCompensation() { return exposureCompensation; }
    public Range<Integer> getExposureRange() { return exposureRange; }

    private void applyExposure() {
        if (previewBuilder == null) return;
        previewBuilder.set(CaptureRequest.CONTROL_AE_EXPOSURE_COMPENSATION, exposureCompensation);
        if (photoBuilder != null) {
            photoBuilder.set(CaptureRequest.CONTROL_AE_EXPOSURE_COMPENSATION, exposureCompensation);
        }
    }

    private void applyProSettings() {
        if (previewBuilder == null) return;
        if (proMode) {
            previewBuilder.set(CaptureRequest.CONTROL_AE_MODE, CaptureRequest.CONTROL_AE_MODE_OFF);
            previewBuilder.set(CaptureRequest.SENSOR_SENSITIVITY, manualISO);
            previewBuilder.set(CaptureRequest.SENSOR_EXPOSURE_TIME, manualShutterSpeed);
            previewBuilder.set(CaptureRequest.CONTROL_AWB_MODE, CaptureRequest.CONTROL_AWB_MODE_OFF);
        } else {
            previewBuilder.set(CaptureRequest.CONTROL_AE_MODE, CaptureRequest.CONTROL_AE_MODE_ON);
            previewBuilder.set(CaptureRequest.CONTROL_AWB_MODE, CaptureRequest.CONTROL_AWB_MODE_AUTO);
        }
    }

    public void setSceneMode(String mode) {
        this.sceneMode = mode;
        if (previewBuilder == null) return;
        try {
            switch (mode) {
                case "hdr":
                    previewBuilder.set(CaptureRequest.CONTROL_SCENE_MODE, CaptureRequest.CONTROL_SCENE_MODE_HDR);
                    break;
                case "night":
                    previewBuilder.set(CaptureRequest.CONTROL_SCENE_MODE, CaptureRequest.CONTROL_SCENE_MODE_NIGHT);
                    break;
                case "portrait":
                    previewBuilder.set(CaptureRequest.CONTROL_SCENE_MODE, CaptureRequest.CONTROL_SCENE_MODE_PORTRAIT);
                    break;
                default:
                    previewBuilder.set(CaptureRequest.CONTROL_SCENE_MODE, CaptureRequest.CONTROL_SCENE_MODE_DISABLED);
                    break;
            }
            applyPreviewSettings();
        } catch (Exception e) {
            Log.e(TAG, "设置场景模式失败", e);
        }
    }

    public String getSceneMode() { return sceneMode; }

    public void takePhoto(OnPhotoTakenListener listener) {
        this.photoListener = listener;
        if (cameraDevice == null || captureSession == null) return;
        try {
            photoBuilder = cameraDevice.createCaptureRequest(CameraDevice.TEMPLATE_STILL_CAPTURE);
            photoBuilder.addTarget(imageReader.getSurface());
            photoBuilder.set(CaptureRequest.JPEG_QUALITY, (byte) 100);
            photoBuilder.set(CaptureRequest.JPEG_ORIENTATION, 90);

            if (previewBuilder.get(CaptureRequest.SCALER_CROP_REGION) != null) {
                photoBuilder.set(CaptureRequest.SCALER_CROP_REGION, previewBuilder.get(CaptureRequest.SCALER_CROP_REGION));
            }
            photoBuilder.set(CaptureRequest.FLASH_MODE, flashMode);
            photoBuilder.set(CaptureRequest.CONTROL_AE_EXPOSURE_COMPENSATION, exposureCompensation);

            if (proMode) {
                photoBuilder.set(CaptureRequest.CONTROL_AE_MODE, CaptureRequest.CONTROL_AE_MODE_OFF);
                photoBuilder.set(CaptureRequest.SENSOR_SENSITIVITY, manualISO);
                photoBuilder.set(CaptureRequest.SENSOR_EXPOSURE_TIME, manualShutterSpeed);
            }

            captureSession.capture(photoBuilder.build(), null, backgroundHandler);
        } catch (CameraAccessException e) {
            Log.e(TAG, "拍照失败", e);
        }
    }

    public void startBurst(int count, OnBurstPhotoListener listener) {
        this.burstMode = true;
        this.burstCount = 0;
        this.burstMax = count;
        this.burstListener = listener;
        takeBurstPhoto();
    }

    private void takeBurstPhoto() {
        if (!burstMode || burstCount >= burstMax || cameraDevice == null) return;
        try {
            CaptureRequest.Builder burstBuilder = cameraDevice.createCaptureRequest(CameraDevice.TEMPLATE_STILL_CAPTURE);
            burstBuilder.addTarget(imageReader.getSurface());
            captureSession.capture(burstBuilder.build(), new CameraCaptureSession.CaptureCallback() {
                @Override
                public void onCaptureCompleted(CameraCaptureSession session, CaptureRequest request, TotalCaptureResult result) {
                    burstCount++;
                    if (burstListener != null) {
                        burstListener.onBurstProgress(burstCount, burstMax);
                    }
                    if (burstCount < burstMax) {
                        backgroundHandler.post(() -> takeBurstPhoto());
                    } else {
                        burstMode = false;
                        if (burstListener != null) burstListener.onBurstComplete(burstCount);
                    }
                }
            }, backgroundHandler);
        } catch (CameraAccessException e) {
            Log.e(TAG, "连拍失败", e);
            burstMode = false;
        }
    }

    public void switchCamera() {
        cameraFacing = cameraFacing == CameraCharacteristics.LENS_FACING_BACK
            ? CameraCharacteristics.LENS_FACING_FRONT
            : CameraCharacteristics.LENS_FACING_BACK;
        releaseCamera();
        start();
    }

    public boolean isFrontCamera() {
        return cameraFacing == CameraCharacteristics.LENS_FACING_FRONT;
    }

    public void setHistogramEnabled(boolean enabled) {
        this.histogramEnabled = enabled;
    }

    public void setHistogramListener(OnHistogramDataListener listener) {
        this.histogramListener = listener;
    }

    private Size chooseOptimalSize(Size[] choices, int targetWidth, int targetHeight) {
        if (choices == null || choices.length == 0) return new Size(targetWidth, targetHeight);
        List<Size> bigEnough = new ArrayList<>();
        for (Size size : choices) {
            if (size.getWidth() >= targetWidth && size.getHeight() >= targetHeight) {
                bigEnough.add(size);
            }
        }
        if (!bigEnough.isEmpty()) {
            return Collections.min(bigEnough, (a, b) ->
                Long.signum((long) a.getWidth() * a.getHeight() - (long) b.getWidth() * b.getHeight()));
        }
        return choices[0];
    }

    private void startBackgroundThread() {
        backgroundThread = new HandlerThread("CameraBackground");
        backgroundThread.start();
        backgroundHandler = new Handler(backgroundThread.getLooper());
    }

    private void stopBackgroundThread() {
        if (backgroundThread != null) {
            backgroundThread.quitSafely();
            try {
                backgroundThread.join();
            } catch (InterruptedException e) {
                e.printStackTrace();
            }
            backgroundThread = null;
            backgroundHandler = null;
        }
    }

    public void releaseCamera() {
        if (captureSession != null) {
            try {
                captureSession.abortCaptures();
            } catch (CameraAccessException e) {
                e.printStackTrace();
            }
            captureSession.close();
            captureSession = null;
        }
        if (cameraDevice != null) {
            cameraDevice.close();
            cameraDevice = null;
        }
        if (imageReader != null) {
            imageReader.close();
            imageReader = null;
        }
    }

    public void stop() {
        releaseCamera();
        stopBackgroundThread();
    }

    public void setOnCameraReadyListener(OnCameraReadyListener listener) {
        this.readyListener = listener;
    }

    public void setOnFocusListener(OnFocusListener listener) {
        this.focusListener = listener;
    }

    public Size getPreviewSize() { return previewSize; }
    public Size getPhotoSize() { return photoSize; }
}
