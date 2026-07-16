package com.agicode.beauty;

import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.Context;
import android.graphics.Bitmap;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.provider.MediaStore;
import android.util.Log;

import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStream;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

/**
 * 相册保存模块 - 华为风格
 * 支持保存照片和视频到系统相册
 */
public class GalleryHelper {

    private static final String TAG = "GalleryHelper";
    private static final String APP_NAME = "AgiBeauty";

    /**
     * 保存照片到相册（兼容 Android 10+ 作用域存储）
     */
    public static Uri savePhoto(Context context, Bitmap bitmap) {
        String timestamp = new SimpleDateFormat("yyyyMMdd_HHmmss", Locale.CHINA).format(new Date());
        String fileName = "IMG_" + timestamp + ".jpg";

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            // Android 10+ 使用 MediaStore
            ContentValues values = new ContentValues();
            values.put(MediaStore.Images.Media.DISPLAY_NAME, fileName);
            values.put(MediaStore.Images.Media.MIME_TYPE, "image/jpeg");
            values.put(MediaStore.Images.Media.RELATIVE_PATH, Environment.DIRECTORY_DCIM + "/" + APP_NAME);
            values.put(MediaStore.Images.Media.IS_PENDING, 1);

            ContentResolver resolver = context.getContentResolver();
            Uri uri = resolver.insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values);

            if (uri != null) {
                try (OutputStream out = resolver.openOutputStream(uri)) {
                    if (out != null) {
                        bitmap.compress(Bitmap.CompressFormat.JPEG, 100, out);
                    }
                    values.clear();
                    values.put(MediaStore.Images.Media.IS_PENDING, 0);
                    resolver.update(uri, values, null, null);
                    Log.d(TAG, "照片已保存: " + uri.toString());
                    return uri;
                } catch (Exception e) {
                    Log.e(TAG, "保存照片失败", e);
                    resolver.delete(uri, null, null);
                }
            }
        } else {
            // Android 9 及以下
            File dir = new File(Environment.getExternalStoragePublicDirectory(
                    Environment.DIRECTORY_DCIM), APP_NAME);
            if (!dir.exists()) dir.mkdirs();

            File file = new File(dir, fileName);
            try (FileOutputStream out = new FileOutputStream(file)) {
                bitmap.compress(Bitmap.CompressFormat.JPEG, 100, out);
                out.flush();

                // 通知相册刷新
                ContentValues values = new ContentValues();
                values.put(MediaStore.Images.Media.DATA, file.getAbsolutePath());
                values.put(MediaStore.Images.Media.MIME_TYPE, "image/jpeg");
                context.getContentResolver().insert(
                        MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values);

                Log.d(TAG, "照片已保存: " + file.getAbsolutePath());
                return Uri.fromFile(file);
            } catch (Exception e) {
                Log.e(TAG, "保存照片失败", e);
            }
        }
        return null;
    }

    /**
     * 创建视频文件 URI（用于 MediaRecorder）
     */
    public static Uri createVideoUri(Context context) {
        String timestamp = new SimpleDateFormat("yyyyMMdd_HHmmss", Locale.CHINA).format(new Date());
        String fileName = "VID_" + timestamp + ".mp4";

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            ContentValues values = new ContentValues();
            values.put(MediaStore.Video.Media.DISPLAY_NAME, fileName);
            values.put(MediaStore.Video.Media.MIME_TYPE, "video/mp4");
            values.put(MediaStore.Video.Media.RELATIVE_PATH, Environment.DIRECTORY_DCIM + "/" + APP_NAME);
            values.put(MediaStore.Video.Media.IS_PENDING, 1);

            ContentResolver resolver = context.getContentResolver();
            Uri uri = resolver.insert(MediaStore.Video.Media.EXTERNAL_CONTENT_URI, values);
            if (uri != null) {
                Log.d(TAG, "视频 URI 已创建: " + uri.toString());
                return uri;
            }
        } else {
            File dir = new File(Environment.getExternalStoragePublicDirectory(
                    Environment.DIRECTORY_DCIM), APP_NAME);
            if (!dir.exists()) dir.mkdirs();
            File file = new File(dir, fileName);
            Log.d(TAG, "视频文件: " + file.getAbsolutePath());
            return Uri.fromFile(file);
        }
        return null;
    }

    /**
     * 视频录制完成后更新 MediaStore
     */
    public static void finalizeVideo(Context context, Uri uri) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q && uri != null) {
            try {
                ContentValues values = new ContentValues();
                values.put(MediaStore.Video.Media.IS_PENDING, 0);
                context.getContentResolver().update(uri, values, null, null);
                Log.d(TAG, "视频已保存到相册");
            } catch (Exception e) {
                Log.e(TAG, "视频保存失败", e);
            }
        }
    }
}
