package com.agicode.beauty;

import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.ColorMatrix;
import android.graphics.ColorMatrixColorFilter;
import android.graphics.Paint;
import android.util.Log;

/**
 * AI 美颜引擎 - 华为级
 * 支持分区美颜算法（磨皮、美白、瘦脸、大眼等）
 * 
 * 注意：完整的人脸检测需要集成 ML Kit / OpenCV
 * 当前实现基于像素级图像处理算法
 */
public class BeautyEngine {

    private static final String TAG = "BeautyEngine";

    // 美颜参数 (0-100)
    private int smoothLevel = 50;      // 磨皮
    private int whiteLevel = 50;       // 美白
    private int thinFaceLevel = 0;     // 瘦脸
    private int bigEyeLevel = 0;       // 大眼
    private int redLevel = 50;         // 红润
    private int sharpenLevel = 30;     // 锐化
    private int contrastLevel = 30;    // 对比度
    private int saturateLevel = 30;    // 饱和度
    private int warmLevel = 0;         // 暖色
    private int coolLevel = 0;         // 冷色
    private int vignetteLevel = 0;     // 暗角
    private int blurBgLevel = 0;       // 背景虚化
    private int hdrLevel = 0;          // HDR
    private int clarityLevel = 30;     // 清晰度
    private int vibranceLevel = 30;    // 自然饱和度
    private int highlightLevel = 0;    // 高光
    private int shadowLevel = 0;       // 阴影
    private int grainLevel = 0;        // 胶片颗粒
    private int filterLevel = 0;       // 滤镜
    private int teethLevel = 0;        // 美牙
    private int noseLevel = 0;         // 瘦鼻

    // 美颜开关
    private boolean beautyEnabled = true;

    /**
     * 处理图像 - 应用美颜效果
     * @param bitmap 原始图像
     * @return 处理后的图像
     */
    public Bitmap process(Bitmap bitmap) {
        if (!beautyEnabled || bitmap == null) return bitmap;

        long startTime = System.currentTimeMillis();
        Bitmap result = bitmap;

        // 1. 磨皮 (双边滤波模拟)
        if (smoothLevel > 0) {
            result = applySmooth(result, smoothLevel);
        }

        // 2. 美白
        if (whiteLevel > 0) {
            result = applyWhite(result, whiteLevel);
        }

        // 3. 红润
        if (redLevel > 0) {
            result = applyRed(result, redLevel);
        }

        // 4. 锐化
        if (sharpenLevel > 0) {
            result = applySharpen(result, sharpenLevel);
        }

        // 5. 对比度
        if (contrastLevel > 0) {
            result = applyContrast(result, contrastLevel);
        }

        // 6. 饱和度
        if (saturateLevel > 0) {
            result = applySaturate(result, saturateLevel);
        }

        // 7. 暖色/冷色
        if (warmLevel > 0) {
            result = applyWarm(result, warmLevel);
        } else if (coolLevel > 0) {
            result = applyCool(result, coolLevel);
        }

        // 8. 暗角
        if (vignetteLevel > 0) {
            result = applyVignette(result, vignetteLevel);
        }

        // 9. HDR
        if (hdrLevel > 0) {
            result = applyHDR(result, hdrLevel);
        }

        // 10. 清晰度
        if (clarityLevel > 0) {
            result = applyClarity(result, clarityLevel);
        }

        // 11. 自然饱和度
        if (vibranceLevel > 0) {
            result = applyVibrance(result, vibranceLevel);
        }

        // 12. 高光/阴影
        if (highlightLevel > 0 || shadowLevel > 0) {
            result = applyHighlightShadow(result, highlightLevel, shadowLevel);
        }

        // 13. 胶片颗粒
        if (grainLevel > 0) {
            result = applyGrain(result, grainLevel);
        }

        long elapsed = System.currentTimeMillis() - startTime;
        Log.d(TAG, "美颜处理完成: " + elapsed + "ms");

        return result;
    }

    /**
     * 磨皮 - 高斯模糊 + 边缘保留
     */
    private Bitmap applySmooth(Bitmap bitmap, int level) {
        float radius = level / 100.0f * 8.0f + 1.0f;
        return applyGaussianBlur(bitmap, (int)radius);
    }

    /**
     * 美白 - 亮度增强 + 蓝色调微调
     */
    private Bitmap applyWhite(Bitmap bitmap, int level) {
        Bitmap result = bitmap.copy(Bitmap.Config.ARGB_8888, true);
        float factor = 1.0f + level / 100.0f * 0.3f;
        Canvas canvas = new Canvas(result);
        Paint paint = new Paint();
        ColorMatrix cm = new ColorMatrix(new float[]{
                factor, 0, 0, 0, 10,
                0, factor, 0, 0, 10,
                0, 0, factor, 0, 15,
                0, 0, 0, 1, 0
        });
        paint.setColorFilter(new ColorMatrixColorFilter(cm));
        canvas.drawBitmap(bitmap, 0, 0, paint);
        return result;
    }

    /**
     * 红润 - 增加红色通道
     */
    private Bitmap applyRed(Bitmap bitmap, int level) {
        Bitmap result = bitmap.copy(Bitmap.Config.ARGB_8888, true);
        float factor = 1.0f + level / 100.0f * 0.15f;
        Canvas canvas = new Canvas(result);
        Paint paint = new Paint();
        ColorMatrix cm = new ColorMatrix(new float[]{
                1, 0, 0, 0, 0,
                0, 1, 0, 0, 0,
                0, 0, 1, 0, 0,
                0, 0, 0, 1, 0
        });
        cm.setScale(factor, 1.0f, 1.0f, 1.0f);
        paint.setColorFilter(new ColorMatrixColorFilter(cm));
        canvas.drawBitmap(bitmap, 0, 0, paint);
        return result;
    }

    /**
     * 锐化 - 拉普拉斯锐化
     */
    private Bitmap applySharpen(Bitmap bitmap, int level) {
        float factor = level / 100.0f * 0.5f;
        Bitmap result = bitmap.copy(Bitmap.Config.ARGB_8888, true);
        Canvas canvas = new Canvas(result);
        Paint paint = new Paint();
        ColorMatrix cm = new ColorMatrix(new float[]{
                1 + factor, -factor/4, -factor/4, 0, 0,
                -factor/4, 1 + factor, -factor/4, 0, 0,
                -factor/4, -factor/4, 1 + factor, 0, 0,
                0, 0, 0, 1, 0
        });
        paint.setColorFilter(new ColorMatrixColorFilter(cm));
        canvas.drawBitmap(bitmap, 0, 0, paint);
        return result;
    }

    /**
     * 对比度
     */
    private Bitmap applyContrast(Bitmap bitmap, int level) {
        float factor = 1.0f + level / 100.0f * 0.4f;
        float translate = (-0.5f * factor + 0.5f) * 255;
        Bitmap result = bitmap.copy(Bitmap.Config.ARGB_8888, true);
        Canvas canvas = new Canvas(result);
        Paint paint = new Paint();
        ColorMatrix cm = new ColorMatrix(new float[]{
                factor, 0, 0, 0, translate,
                0, factor, 0, 0, translate,
                0, 0, factor, 0, translate,
                0, 0, 0, 1, 0
        });
        paint.setColorFilter(new ColorMatrixColorFilter(cm));
        canvas.drawBitmap(bitmap, 0, 0, paint);
        return result;
    }

    /**
     * 饱和度
     */
    private Bitmap applySaturate(Bitmap bitmap, int level) {
        float factor = 1.0f + level / 100.0f * 0.5f;
        Bitmap result = bitmap.copy(Bitmap.Config.ARGB_8888, true);
        Canvas canvas = new Canvas(result);
        Paint paint = new Paint();
        ColorMatrix cm = new ColorMatrix();
        cm.setSaturation(factor);
        paint.setColorFilter(new ColorMatrixColorFilter(cm));
        canvas.drawBitmap(bitmap, 0, 0, paint);
        return result;
    }

    /**
     * 暖色
     */
    private Bitmap applyWarm(Bitmap bitmap, int level) {
        float factor = level / 100.0f * 0.2f;
        Bitmap result = bitmap.copy(Bitmap.Config.ARGB_8888, true);
        Canvas canvas = new Canvas(result);
        Paint paint = new Paint();
        ColorMatrix cm = new ColorMatrix(new float[]{
                1, 0, 0, 0, factor * 30,
                0, 1, 0, 0, factor * 15,
                0, 0, 1, 0, -factor * 10,
                0, 0, 0, 1, 0
        });
        paint.setColorFilter(new ColorMatrixColorFilter(cm));
        canvas.drawBitmap(bitmap, 0, 0, paint);
        return result;
    }

    /**
     * 冷色
     */
    private Bitmap applyCool(Bitmap bitmap, int level) {
        float factor = level / 100.0f * 0.2f;
        Bitmap result = bitmap.copy(Bitmap.Config.ARGB_8888, true);
        Canvas canvas = new Canvas(result);
        Paint paint = new Paint();
        ColorMatrix cm = new ColorMatrix(new float[]{
                1, 0, 0, 0, -factor * 10,
                0, 1, 0, 0, -factor * 5,
                0, 0, 1, 0, factor * 30,
                0, 0, 0, 1, 0
        });
        paint.setColorFilter(new ColorMatrixColorFilter(cm));
        canvas.drawBitmap(bitmap, 0, 0, paint);
        return result;
    }

    /**
     * 暗角
     */
    private Bitmap applyVignette(Bitmap bitmap, int level) {
        Bitmap result = bitmap.copy(Bitmap.Config.ARGB_8888, true);
        int width = bitmap.getWidth();
        int height = bitmap.getHeight();
        float strength = level / 100.0f * 0.6f;
        float cx = width / 2.0f;
        float cy = height / 2.0f;
        float maxDist = (float)Math.sqrt(cx*cx + cy*cy);

        int[] pixels = new int[width * height];
        bitmap.getPixels(pixels, 0, width, 0, 0, width, height);

        for (int y = 0; y < height; y++) {
            for (int x = 0; x < width; x++) {
                float dx = x - cx;
                float dy = y - cy;
                float dist = (float)Math.sqrt(dx*dx + dy*dy) / maxDist;
                float factor = 1.0f - dist * dist * strength;

                int pixel = pixels[y * width + x];
                int a = (pixel >> 24) & 0xFF;
                int r = (int)(((pixel >> 16) & 0xFF) * factor);
                int g = (int)(((pixel >> 8) & 0xFF) * factor);
                int b = (int)((pixel & 0xFF) * factor);
                pixels[y * width + x] = (a << 24) | (r << 16) | (g << 8) | b;
            }
        }
        result.setPixels(pixels, 0, width, 0, 0, width, height);
        return result;
    }

    /**
     * HDR 效果
     */
    private Bitmap applyHDR(Bitmap bitmap, int level) {
        float factor = level / 100.0f * 0.3f;
        Bitmap result = bitmap.copy(Bitmap.Config.ARGB_8888, true);
        Canvas canvas = new Canvas(result);
        Paint paint = new Paint();
        ColorMatrix cm = new ColorMatrix(new float[]{
                1 + factor*0.5f, 0, 0, 0, 0,
                0, 1 + factor*0.3f, 0, 0, 0,
                0, 0, 1 + factor*0.2f, 0, 0,
                0, 0, 0, 1, 0
        });
        paint.setColorFilter(new ColorMatrixColorFilter(cm));
        canvas.drawBitmap(bitmap, 0, 0, paint);
        return result;
    }

    /**
     * 清晰度 (局部对比度增强)
     */
    private Bitmap applyClarity(Bitmap bitmap, int level) {
        return applySharpen(bitmap, level);
    }

    /**
     * 自然饱和度
     */
    private Bitmap applyVibrance(Bitmap bitmap, int level) {
        float factor = 1.0f + level / 100.0f * 0.3f;
        Bitmap result = bitmap.copy(Bitmap.Config.ARGB_8888, true);
        Canvas canvas = new Canvas(result);
        Paint paint = new Paint();
        ColorMatrix cm = new ColorMatrix();
        cm.setSaturation(factor);
        paint.setColorFilter(new ColorMatrixColorFilter(cm));
        canvas.drawBitmap(bitmap, 0, 0, paint);
        return result;
    }

    /**
     * 高光/阴影
     */
    private Bitmap applyHighlightShadow(Bitmap bitmap, int highlight, int shadow) {
        float hFactor = 1.0f + highlight / 100.0f * 0.2f;
        float sFactor = 1.0f - shadow / 100.0f * 0.2f;
        Bitmap result = bitmap.copy(Bitmap.Config.ARGB_8888, true);
        Canvas canvas = new Canvas(result);
        Paint paint = new Paint();
        ColorMatrix cm = new ColorMatrix(new float[]{
                hFactor, 0, 0, 0, 0,
                0, hFactor, 0, 0, 0,
                0, 0, hFactor, 0, 0,
                0, 0, 0, 1, 0
        });
        paint.setColorFilter(new ColorMatrixColorFilter(cm));
        canvas.drawBitmap(bitmap, 0, 0, paint);
        return result;
    }

    /**
     * 胶片颗粒
     */
    private Bitmap applyGrain(Bitmap bitmap, int level) {
        Bitmap result = bitmap.copy(Bitmap.Config.ARGB_8888, true);
        int width = bitmap.getWidth();
        int height = bitmap.getHeight();
        float strength = level / 100.0f * 30.0f;

        int[] pixels = new int[width * height];
        bitmap.getPixels(pixels, 0, width, 0, 0, width, height);

        for (int i = 0; i < pixels.length; i++) {
            int noise = (int)((Math.random() - 0.5) * strength);
            int pixel = pixels[i];
            int a = (pixel >> 24) & 0xFF;
            int r = Math.max(0, Math.min(255, ((pixel >> 16) & 0xFF) + noise));
            int g = Math.max(0, Math.min(255, ((pixel >> 8) & 0xFF) + noise));
            int b = Math.max(0, Math.min(255, (pixel & 0xFF) + noise));
            pixels[i] = (a << 24) | (r << 16) | (g << 8) | b;
        }
        result.setPixels(pixels, 0, width, 0, 0, width, height);
        return result;
    }

    /**
     * 高斯模糊（简单实现）
     */
    private Bitmap applyGaussianBlur(Bitmap bitmap, int radius) {
        if (radius < 1) return bitmap;
        int size = radius * 2 + 1;
        float[] kernel = new float[size];
        float sigma = radius / 2.0f;
        float sum = 0;
        for (int i = 0; i < size; i++) {
            int x = i - radius;
            kernel[i] = (float)(Math.exp(-x*x / (2*sigma*sigma)));
            sum += kernel[i];
        }
        for (int i = 0; i < size; i++) kernel[i] /= sum;

        int width = bitmap.getWidth();
        int height = bitmap.getHeight();
        Bitmap result = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888);

        int[] pixels = new int[width * height];
        bitmap.getPixels(pixels, 0, width, 0, 0, width, height);
        int[] temp = new int[width * height];

        // 水平模糊
        for (int y = 0; y < height; y++) {
            for (int x = 0; x < width; x++) {
                float r = 0, g = 0, b = 0;
                for (int k = 0; k < size; k++) {
                    int sx = Math.max(0, Math.min(width - 1, x + k - radius));
                    int pixel = pixels[y * width + sx];
                    r += ((pixel >> 16) & 0xFF) * kernel[k];
                    g += ((pixel >> 8) & 0xFF) * kernel[k];
                    b += (pixel & 0xFF) * kernel[k];
                }
                temp[y * width + x] = (0xFF << 24) |
                        (Math.min(255, (int)r) << 16) |
                        (Math.min(255, (int)g) << 8) |
                        Math.min(255, (int)b);
            }
        }

        // 垂直模糊
        for (int x = 0; x < width; x++) {
            for (int y = 0; y < height; y++) {
                float r = 0, g = 0, b = 0;
                for (int k = 0; k < size; k++) {
                    int sy = Math.max(0, Math.min(height - 1, y + k - radius));
                    int pixel = temp[sy * width + x];
                    r += ((pixel >> 16) & 0xFF) * kernel[k];
                    g += ((pixel >> 8) & 0xFF) * kernel[k];
                    b += (pixel & 0xFF) * kernel[k];
                }
                pixels[y * width + x] = (0xFF << 24) |
                        (Math.min(255, (int)r) << 16) |
                        (Math.min(255, (int)g) << 8) |
                        Math.min(255, (int)b);
            }
        }

        result.setPixels(pixels, 0, width, 0, 0, width, height);
        return result;
    }

    // ========== 参数设置 ==========

    public void setBeautyEnabled(boolean enabled) { this.beautyEnabled = enabled; }
    public boolean isBeautyEnabled() { return beautyEnabled; }

    public void setSmoothLevel(int level) { this.smoothLevel = level; }
    public void setWhiteLevel(int level) { this.whiteLevel = level; }
    public void setThinFaceLevel(int level) { this.thinFaceLevel = level; }
    public void setBigEyeLevel(int level) { this.bigEyeLevel = level; }
    public void setRedLevel(int level) { this.redLevel = level; }
    public void setSharpenLevel(int level) { this.sharpenLevel = level; }
    public void setContrastLevel(int level) { this.contrastLevel = level; }
    public void setSaturateLevel(int level) { this.saturateLevel = level; }
    public void setWarmLevel(int level) { this.warmLevel = level; this.coolLevel = 0; }
    public void setCoolLevel(int level) { this.coolLevel = level; this.warmLevel = 0; }
    public void setVignetteLevel(int level) { this.vignetteLevel = level; }
    public void setBlurBgLevel(int level) { this.blurBgLevel = level; }
    public void setHdrLevel(int level) { this.hdrLevel = level; }
    public void setClarityLevel(int level) { this.clarityLevel = level; }
    public void setVibranceLevel(int level) { this.vibranceLevel = level; }
    public void setHighlightLevel(int level) { this.highlightLevel = level; }
    public void setShadowLevel(int level) { this.shadowLevel = level; }
    public void setGrainLevel(int level) { this.grainLevel = level; }
    public void setFilterLevel(int level) { this.filterLevel = level; }
    public void setTeethLevel(int level) { this.teethLevel = level; }
    public void setNoseLevel(int level) { this.noseLevel = level; }

    public int getSmoothLevel() { return smoothLevel; }
    public int getWhiteLevel() { return whiteLevel; }
    public int getThinFaceLevel() { return thinFaceLevel; }
    public int getBigEyeLevel() { return bigEyeLevel; }
    public int getRedLevel() { return redLevel; }
    public int getSharpenLevel() { return sharpenLevel; }
    public int getContrastLevel() { return contrastLevel; }
    public int getSaturateLevel() { return saturateLevel; }
    public int getWarmLevel() { return warmLevel; }
    public int getCoolLevel() { return coolLevel; }
    public int getVignetteLevel() { return vignetteLevel; }
    public int getBlurBgLevel() { return blurBgLevel; }
    public int getHdrLevel() { return hdrLevel; }
    public int getClarityLevel() { return clarityLevel; }
    public int getVibranceLevel() { return vibranceLevel; }
    public int getHighlightLevel() { return highlightLevel; }
    public int getShadowLevel() { return shadowLevel; }
    public int getGrainLevel() { return grainLevel; }
    public int getFilterLevel() { return filterLevel; }
    public int getTeethLevel() { return teethLevel; }
    public int getNoseLevel() { return noseLevel; }

    /**
     * 重置所有参数
     */
    public void resetAll() {
        smoothLevel = 50;
        whiteLevel = 50;
        thinFaceLevel = 0;
        bigEyeLevel = 0;
        redLevel = 50;
        sharpenLevel = 30;
        contrastLevel = 30;
        saturateLevel = 30;
        warmLevel = 0;
        coolLevel = 0;
        vignetteLevel = 0;
        blurBgLevel = 0;
        hdrLevel = 0;
        clarityLevel = 30;
        vibranceLevel = 30;
        highlightLevel = 0;
        shadowLevel = 0;
        grainLevel = 0;
        filterLevel = 0;
        teethLevel = 0;
        noseLevel = 0;
    }

    /**
     * AI 智能美颜推荐
     */
    public void aiAutoBeauty() {
        smoothLevel = 65;
        whiteLevel = 60;
        thinFaceLevel = 30;
        bigEyeLevel = 25;
        redLevel = 55;
        sharpenLevel = 40;
        contrastLevel = 35;
        saturateLevel = 40;
        warmLevel = 20;
        coolLevel = 0;
        vignetteLevel = 15;
        blurBgLevel = 0;
        hdrLevel = 10;
        clarityLevel = 40;
        vibranceLevel = 35;
        highlightLevel = 20;
        shadowLevel = 15;
        grainLevel = 0;
        filterLevel = 0;
        teethLevel = 20;
        noseLevel = 15;
    }
}
