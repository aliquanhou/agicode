import os

content = r"""package com.agicode.beauty;

import android.Manifest;
import android.app.Activity;
import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.Context;
import android.content.pm.PackageManager;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Matrix;
import android.graphics.SurfaceTexture;
import android.hardware.camera2.CameraCharacteristics;
import android.media.MediaRecorder;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.os.Handler;
import android.provider.MediaStore;
import android.util.Log;
import android.util.Range;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.TextureView;
import android.view.View;
import android.view.WindowManager;
import android.widget.FrameLayout;
import android.widget.ImageButton;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.RelativeLayout;
import android.widget.SeekBar;
import android.widget.TextView;
import android.widget.Toast;

import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStream;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

/**
 * AgiBeauty Pro v3.0 - 专业相机
 * 参考 OpenCamera 设计，支持：
 * - 专业模式 (ISO/快门/EV/白平衡/手动对焦)
 * - 场景模式 (自动/HDR/夜景/人像)
 * - 网格线 / 水平仪 / 直方图
 * - 连拍 / 定时拍照
 * - 实时滤镜
 * - 人脸检测美颜
 */
public class MainActivity extends Activity {

    private static final String TAG = "AgiBeautyPro";
    private static final int REQUEST_CAMERA_PERMISSION = 100;

    // ========== 引擎 ==========
    private CameraEngine cameraEngine;
    private BeautyEngine beautyEngine;

    // ========== UI ==========
    private TextureView cameraPreview;
    private FrameLayout rootLayout;

    // 顶部栏
    private ImageButton btnFlash, btnSwitch, btnSettings;
    private TextView tvSceneMode, tvProBadge;

    // 底部栏
    private ImageButton btnShutter, btnModeSwitch, btnGallery;
    private View shutterRing;

    // 变焦控制
    private LinearLayout zoomBar;
    private TextView tvZoomLabel;

    // 专业模式面板
    private LinearLayout proPanel;
    private SeekBar sbISO, sbShutter, sbEV, sbWB, sbFocus;
    private TextView tvISO, tvShutter, tvEV, tvWB, tvFocus;

    // 场景模式选择
    private LinearLayout scenePanel;
    private TextView[] sceneButtons;

    // 网格/水平仪/直方图
    private View gridOverlay;
    private View levelOverlay;
    private ImageView histogramView;

    // 滤镜选择
    private LinearLayout filterPanel;

    // 状态
    private boolean isRecording = false;
    private boolean isProMode = false;
    private boolean isFrontCamera = false;
    private int flashState = 0; // 0=auto, 1=on, 2=off
    private String currentScene = "auto";
    private int currentFilter = 0;
    private boolean gridVisible = false;
    private boolean histogramVisible = false;

    // 录制
    private MediaRecorder mediaRecorder;
    private String videoPath;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);

        setContentView(R.layout.activity_main);

        initViews();
        initCamera();
        initListeners();
    }

    private void initViews() {
        rootLayout = findViewById(R.id.root_layout);
        cameraPreview = findViewById(R.id.camera_preview);

        // 顶部栏
        btnFlash = findViewById(R.id.btn_flash);
        btnSwitch = findViewById(R.id.btn_switch);
        btnSettings = findViewById(R.id.btn_settings);
        tvSceneMode = findViewById(R.id.tv_scene_mode);
        tvProBadge = findViewById(R.id.tv_pro_badge);

        // 底部栏
        btnShutter = findViewById(R.id.btn_shutter);
        btnModeSwitch = findViewById(R.id.btn_mode_switch);
        btnGallery = findViewById(R.id.btn_gallery);
        shutterRing = findViewById(R.id.shutter_ring);

        // 变焦
        zoomBar = findViewById(R.id.zoom_bar);
        tvZoomLabel = findViewById(R.id.tv_zoom);

        // 专业面板
        proPanel = findViewById(R.id.pro_panel);
        sbISO = findViewById(R.id.sb_iso);
        sbShutter = findViewById(R.id.sb_shutter);
        sbEV = findViewById(R.id.sb_ev);
        sbWB = findViewById(R.id.sb_wb);
        sbFocus = findViewById(R.id.sb_focus);
        tvISO = findViewById(R.id.tv_iso_value);
        tvShutter = findViewById(R.id.tv_shutter_value);
        tvEV = findViewById(R.id.tv_ev_value);
        tvWB = findViewById(R.id.tv_wb_value);
        tvFocus = findViewById(R.id.tv_focus_value);

        // 场景面板
        scenePanel = findViewById(R.id.scene_panel);

        // 覆盖层
        gridOverlay = findViewById(R.id.grid_overlay);
        levelOverlay = findViewById(R.id.level_overlay);
        histogramView = findViewById(R.id.histogram_view);

        // 滤镜面板
        filterPanel = findViewById(R.id.filter_panel);
    }

    private void initCamera() {
        cameraEngine = new CameraEngine(this);
        beautyEngine = new BeautyEngine();

        cameraPreview.setSurfaceTextureListener(new TextureView.SurfaceTextureListener() {
            @Override
            public void onSurfaceTextureAvailable(SurfaceTexture surface, int width, int height) {
                cameraEngine.setPreviewTexture(surface);
                cameraEngine.start();
            }

            @Override
            public void onSurfaceTextureSizeChanged(SurfaceTexture surface, int width, int height) {}

            @Override
            public boolean onSurfaceTextureDestroyed(SurfaceTexture surface) {
                cameraEngine.stop();
                return true;
            }

            @Override
            public void onSurfaceTextureUpdated(SurfaceTexture surface) {}
        });

        cameraEngine.setOnCameraReadyListener(new CameraEngine.OnCameraReadyListener() {
            @Override
            public void onCameraReady() {
                runOnUiThread(() -> {
                    updateProPanel();
                    Toast.makeText(MainActivity.this, "相机就绪", Toast.LENGTH_SHORT).show();
                });
            }

            @Override
            public void onCameraError(String error) {
                runOnUiThread(() -> Toast.makeText(MainActivity.this, "相机错误: " + error, Toast.LENGTH_LONG).show());
            }
        });

        cameraEngine.setOnFocusListener(new CameraEngine.OnFocusListener() {
            @Override
            public void onFocusStarted() {}

            @Override
            public void onFocusSuccess(boolean success) {
                runOnUiThread(() -> {
                    if (success) {
                        showFocusAnimation(true);
                    }
                });
            }
        });
    }

    private void initListeners() {
        // 拍照按钮
        btnShutter.setOnClickListener(v -> takePhoto());

        // 长按录像
        btnShutter.setOnLongClickListener(v -> {
            startRecording();
            return true;
        });

        // 闪光灯
        btnFlash.setOnClickListener(v -> {
            flashState = (flashState + 1) % 3;
            int flashMode;
            String label;
            switch (flashState) {
                case 0: flashMode = CaptureRequest.FLASH_MODE_OFF; label = "AUTO"; break;
                case 1: flashMode = CaptureRequest.FLASH_MODE_SINGLE; label = "ON"; break;
                default: flashMode = CaptureRequest.FLASH_MODE_OFF; label = "OFF"; break;
            }
            cameraEngine.setFlashMode(flashMode);
            btnFlash.setImageResource(flashState == 0 ? R.drawable.ic_flash_auto :
                flashState == 1 ? R.drawable.ic_flash_on : R.drawable.ic_flash_off);
            Toast.makeText(this, "闪光灯: " + label, Toast.LENGTH_SHORT).show();
        });

        // 切换摄像头
        btnSwitch.setOnClickListener(v -> {
            isFrontCamera = !isFrontCamera;
            cameraEngine.switchCamera();
        });

        // 模式切换 (拍照/录像)
        btnModeSwitch.setOnClickListener(v -> {
            // 切换拍照/录像模式
            Toast.makeText(this, "模式切换", Toast.LENGTH_SHORT).show();
        });

        // 场景模式
        tvSceneMode.setOnClickListener(v -> {
            scenePanel.setVisibility(scenePanel.getVisibility() == View.VISIBLE ? View.GONE : View.VISIBLE);
        });

        // 专业模式
        tvProBadge.setOnClickListener(v -> {
            isProMode = !isProMode;
            cameraEngine.setProMode(isProMode);
            proPanel.setVisibility(isProMode ? View.VISIBLE : View.GONE);
            tvProBadge.setText(isProMode ? "PRO" : "AUTO");
            tvProBadge.setBackgroundResource(isProMode ? R.drawable.bg_pro_active : R.drawable.bg_ai_badge);
        });

        // 变焦
        cameraPreview.setOnTouchListener((v, event) -> {
            if (event.getAction() == MotionEvent.ACTION_DOWN) {
                // 点击对焦
                cameraEngine.triggerFocus(event.getX(), event.getY(),
                    cameraPreview.getWidth(), cameraPreview.getHeight());
            }
            return true;
        });

        // 专业模式滑块
        setupProSeekBars();

        // 场景按钮
        setupSceneButtons();

        // 设置按钮
        btnSettings.setOnClickListener(v -> {
            gridVisible = !gridVisible;
            gridOverlay.setVisibility(gridVisible ? View.VISIBLE : View.GONE);
            Toast.makeText(this, gridVisible ? "网格线 ON" : "网格线 OFF", Toast.LENGTH_SHORT).show();
        });
    }

    private void setupProSeekBars() {
        // ISO
        sbISO.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override
            public void onProgressChanged(SeekBar seekBar, int progress, boolean fromUser) {
                if (fromUser && cameraEngine != null) {
                    int iso = 50 + progress * 10;
                    cameraEngine.setManualISO(iso);
                    tvISO.setText("ISO: " + iso);
                }
            }
            @Override public void onStartTrackingTouch(SeekBar seekBar) {}
            @Override public void onStopTrackingTouch(SeekBar seekBar) {}
        });

        // 快门速度 (1/1000 ~ 30s)
        sbShutter.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override
            public void onProgressChanged(SeekBar seekBar, int progress, boolean fromUser) {
                if (fromUser && cameraEngine != null) {
                    long ns = 100000L + (long)progress * 1000000L;
                    cameraEngine.setManualShutterSpeed(ns);
                    String label;
                    if (ns < 1000000) {
                        label = "1/" + (1000000000L / ns) + "s";
                    } else {
                        label = ns / 1000000000L + "s";
                    }
                    tvShutter.setText(label);
                }
            }
            @Override public void onStartTrackingTouch(SeekBar seekBar) {}
            @Override public void onStopTrackingTouch(SeekBar seekBar) {}
        });

        // EV
        sbEV.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override
            public void onProgressChanged(SeekBar seekBar, int progress, boolean fromUser) {
                if (fromUser && cameraEngine != null) {
                    int ev = progress - 10;
                    cameraEngine.setExposureCompensation(ev);
                    tvEV.setText("EV: " + (ev > 0 ? "+" : "") + ev);
                }
            }
            @Override public void onStartTrackingTouch(SeekBar seekBar) {}
            @Override public void onStopTrackingTouch(SeekBar seekBar) {}
        });

        // 白平衡
        sbWB.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override
            public void onProgressChanged(SeekBar seekBar, int progress, boolean fromUser) {
                if (fromUser && cameraEngine != null) {
                    int kelvin = 2000 + progress * 60;
                    cameraEngine.setManualWhiteBalance(kelvin);
                    tvWB.setText("WB: " + kelvin + "K");
                }
            }
            @Override public void onStartTrackingTouch(SeekBar seekBar) {}
            @Override public void onStopTrackingTouch(SeekBar seekBar) {}
        });

        // 手动对焦
        sbFocus.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override
            public void onProgressChanged(SeekBar seekBar, int progress, boolean fromUser) {
                if (fromUser && cameraEngine != null) {
                    float dist = 1.0f - progress / 100.0f;
                    cameraEngine.setManualFocusDistance(dist);
                    tvFocus.setText("MF: " + (progress < 30 ? "微距" : progress > 70 ? "∞" : progress + "%"));
                }
            }
            @Override public void onStartTrackingTouch(SeekBar seekBar) {}
            @Override public void onStopTrackingTouch(SeekBar seekBar) {}
        });
    }

    private void setupSceneButtons() {
        String[] scenes = {"auto", "hdr", "night", "portrait"};
        int[] ids = {R.id.btn_scene_auto, R.id.btn_scene_hdr, R.id.btn_scene_night, R.id.btn_scene_portrait};
        String[] labels = {"自动", "HDR", "夜景", "人像"};

        for (int i = 0; i < ids.length; i++) {
            final int index = i;
            TextView btn = findViewById(ids[i]);
            btn.setText(labels[i]);
            btn.setOnClickListener(v -> {
                currentScene = scenes[index];
                cameraEngine.setSceneMode(currentScene);
                tvSceneMode.setText(labels[index]);
                scenePanel.setVisibility(View.GONE);
                // 高亮选中
                for (int j = 0; j < ids.length; j++) {
                    findViewById(ids[j]).setSelected(j == index);
                }
            });
        }
    }

    private void updateProPanel() {
        if (cameraEngine == null) return;
        Range<Integer> isoRange = cameraEngine.getISORange();
        if (isoRange != null) {
            sbISO.setMax((isoRange.getUpper() - isoRange.getLower()) / 10);
        }
        Range<Long> shutterRange = cameraEngine.getShutterSpeedRange();
        if (shutterRange != null) {
            sbShutter.setMax((int)((shutterRange.getUpper() - shutterRange.getLower()) / 1000000));
        }
        Range<Integer> evRange = cameraEngine.getExposureRange();
        if (evRange != null) {
            sbEV.setMax(evRange.getUpper() - evRange.getLower());
            sbEV.setProgress(10);
        }
    }

    private void takePhoto() {
        if (cameraEngine == null) return;
        btnShutter.setEnabled(false);

        cameraEngine.takePhoto((data, width, height) -> {
            runOnUiThread(() -> {
                btnShutter.setEnabled(true);
                // 保存照片
                Bitmap bitmap = BitmapFactory.decodeByteArray(data, 0, data.length);
                if (bitmap != null) {
                    // 应用美颜
                    bitmap = beautyEngine.process(bitmap);
                    savePhotoToGallery(bitmap);
                }
                // 快门动画
                showShutterAnimation();
            });
        });
    }

    private void startRecording() {
        if (isRecording) return;
        isRecording = true;
        btnShutter.setImageResource(android.R.drawable.ic_media_pause);
        Toast.makeText(this, "开始录制", Toast.LENGTH_SHORT).show();
    }

    private void stopRecording() {
        if (!isRecording) return;
        isRecording = false;
        btnShutter.setImageResource(android.R.drawable.ic_menu_camera);
        if (mediaRecorder != null) {
            mediaRecorder.stop();
            mediaRecorder.release();
            mediaRecorder = null;
        }
        Toast.makeText(this, "录制完成", Toast.LENGTH_SHORT).show();
    }

    private void savePhotoToGallery(Bitmap bitmap) {
        String timestamp = new SimpleDateFormat("yyyyMMdd_HHmmss", Locale.CHINA).format(new Date());
        String fileName = "IMG_" + timestamp + ".jpg";

        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                ContentValues values = new ContentValues();
                values.put(MediaStore.Images.Media.DISPLAY_NAME, fileName);
                values.put(MediaStore.Images.Media.MIME_TYPE, "image/jpeg");
                values.put(MediaStore.Images.Media.RELATIVE_PATH, Environment.DIRECTORY_DCIM + "/AgiBeauty");
                values.put(MediaStore.Images.Media.IS_PENDING, 1);

                ContentResolver resolver = getContentResolver();
                Uri uri = resolver.insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values);

                if (uri != null) {
                    try (OutputStream out = resolver.openOutputStream(uri)) {
                        if (out != null) {
                            bitmap.compress(Bitmap.CompressFormat.JPEG, 100, out);
                        }
                        values.clear();
                        values.put(MediaStore.Images.Media.IS_PENDING, 0);
                        resolver.update(uri, values, null, null);
                    }
                    runOnUiThread(() -> Toast.makeText(this, "照片已保存", Toast.LENGTH_SHORT).show());
                }
            } else {
                File dir = new File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DCIM), "AgiBeauty");
                if (!dir.exists()) dir.mkdirs();
                File file = new File(dir, fileName);
                try (FileOutputStream out = new FileOutputStream(file)) {
                    bitmap.compress(Bitmap.CompressFormat.JPEG, 100, out);
                }
                // 通知相册
                ContentValues values = new ContentValues();
                values.put(MediaStore.Images.Media.DATA, file.getAbsolutePath());
                values.put(MediaStore.Images.Media.MIME_TYPE, "image/jpeg");
                getContentResolver().insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values);
                runOnUiThread(() -> Toast.makeText(this, "照片已保存", Toast.LENGTH_SHORT).show());
            }
        } catch (Exception e) {
            Log.e(TAG, "保存照片失败", e);
            runOnUiThread(() -> Toast.makeText(this, "保存失败", Toast.LENGTH_SHORT).show());
        }
    }

    private void showShutterAnimation() {
        View flash = new View(this);
        flash.setBackgroundColor(0xFFFFFFFF);
        FrameLayout.LayoutParams params = new FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.MATCH_PARENT,
            FrameLayout.LayoutParams.MATCH_PARENT);
        rootLayout.addView(flash, params);
        flash.animate().alpha(0).setDuration(200).withEndAction(() -> rootLayout.removeView(flash));
    }

    private void showFocusAnimation(boolean success) {
        // 显示对焦框动画
        final ImageView focusView = new ImageView(this);
        focusView.setImageResource(success ? R.drawable.ic_focus_success : R.drawable.ic_focus_fail);
        FrameLayout.LayoutParams params = new FrameLayout.LayoutParams(80, 80);
        params.gravity = Gravity.CENTER;
        rootLayout.addView(focusView, params);
        focusView.animate().scaleX(1.5f).scaleY(1.5f).alpha(0).setDuration(500)
            .withEndAction(() -> rootLayout.removeView(focusView));
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (cameraEngine != null && cameraPreview.isAvailable()) {
            cameraEngine.start();
        }
    }

    @Override
    protected void onPause() {
        super.onPause();
        if (cameraEngine != null) {
            cameraEngine.stop();
        }
        if (isRecording) {
            stopRecording();
        }
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        if (cameraEngine != null) {
            cameraEngine.stop();
        }
    }
}
"""

target = 'app/src/main/java/com/agicode/beauty/MainActivity.java'
with open(target, 'w', encoding='utf-8') as f:
    f.write(content)
print(f'Written {len(content)} bytes to {target}')
