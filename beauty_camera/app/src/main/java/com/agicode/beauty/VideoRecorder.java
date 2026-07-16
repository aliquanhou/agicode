package com.agicode.beauty;

import android.content.Context;
import android.hardware.camera2.CameraCharacteristics;
import android.media.MediaRecorder;
import android.net.Uri;
import android.os.Build;
import android.util.Log;
import android.view.Surface;

public class VideoRecorder {
    private static final String TAG = "VideoRecorder";
    private MediaRecorder mediaRecorder;
    private boolean isRecording = false;
    private boolean isPaused = false;
    private Uri outputUri;
    private Context context;
    private int videoWidth = 1920;
    private int videoHeight = 1080;
    private int bitrate = 20 * 1000 * 1000;
    private int frameRate = 30;
    public static final int QUALITY_720P = 0;
    public static final int QUALITY_1080P = 1;
    public static final int QUALITY_4K = 2;
    private OnRecordingListener recordingListener;

    public interface OnRecordingListener {
        void onRecordingStarted(Uri uri);
        void onRecordingPaused();
        void onRecordingResumed();
        void onRecordingStopped(Uri uri, long durationMs);
        void onRecordingError(String error);
    }

    public VideoRecorder(Context context) { this.context = context; }

    public void setQuality(int quality) {
        switch (quality) {
            case QUALITY_720P: videoWidth = 1280; videoHeight = 720; bitrate = 10*1000*1000; frameRate = 30; break;
            case QUALITY_1080P: videoWidth = 1920; videoHeight = 1080; bitrate = 20*1000*1000; frameRate = 30; break;
            case QUALITY_4K: videoWidth = 3840; videoHeight = 2160; bitrate = 50*1000*1000; frameRate = 30; break;
        }
    }

    public boolean startRecording(int cameraFacing) {
        if (isRecording) return false;
        try {
            outputUri = GalleryHelper.createVideoUri(context);
            if (outputUri == null) {
                if (recordingListener != null) recordingListener.onRecordingError("Cannot create video file");
                return false;
            }
            mediaRecorder = new MediaRecorder();
            mediaRecorder.setAudioSource(MediaRecorder.AudioSource.MIC);
            mediaRecorder.setVideoSource(MediaRecorder.VideoSource.SURFACE);
            mediaRecorder.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4);
            mediaRecorder.setAudioEncoder(MediaRecorder.AudioEncoder.AAC);
            mediaRecorder.setAudioChannels(2);
            mediaRecorder.setAudioSamplingRate(44100);
            mediaRecorder.setVideoEncoder(MediaRecorder.VideoEncoder.H264);
            mediaRecorder.setVideoFrameRate(frameRate);
            mediaRecorder.setVideoSize(videoWidth, videoHeight);
            mediaRecorder.setVideoEncodingBitRate(bitrate);
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                mediaRecorder.setOutputFile(context.getContentResolver().openFileDescriptor(outputUri, "w").getFileDescriptor());
            } else {
                mediaRecorder.setOutputFile(outputUri.getPath());
            }
            int rotation = (cameraFacing == CameraCharacteristics.LENS_FACING_FRONT) ? 270 : 90;
            mediaRecorder.setOrientationHint(rotation);
            mediaRecorder.prepare();
            mediaRecorder.start();
            isRecording = true;
            isPaused = false;
            Log.d(TAG, "Recording started: " + videoWidth + "x" + videoHeight);
            if (recordingListener != null) recordingListener.onRecordingStarted(outputUri);
            return true;
        } catch (Exception e) {
            Log.e(TAG, "Start recording failed", e);
            if (recordingListener != null) recordingListener.onRecordingError(e.getMessage());
            release();
            return false;
        }
    }

    public boolean pauseRecording() {
        if (!isRecording || isPaused) return false;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
            try { mediaRecorder.pause(); isPaused = true; if (recordingListener != null) recordingListener.onRecordingPaused(); return true; }
            catch (Exception e) { Log.e(TAG, "Pause failed", e); }
        }
        return false;
    }

    public boolean resumeRecording() {
        if (!isRecording || !isPaused) return false;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
            try { mediaRecorder.resume(); isPaused = false; if (recordingListener != null) recordingListener.onRecordingResumed(); return true; }
            catch (Exception e) { Log.e(TAG, "Resume failed", e); }
        }
        return false;
    }

    public Uri stopRecording() {
        if (!isRecording) return null;
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N && isPaused) mediaRecorder.resume();
            mediaRecorder.stop();
            mediaRecorder.reset();
            mediaRecorder.release();
            mediaRecorder = null;
            isRecording = false;
            isPaused = false;
            GalleryHelper.finalizeVideo(context, outputUri);
            if (recordingListener != null) recordingListener.onRecordingStopped(outputUri, 0);
            return outputUri;
        } catch (Exception e) {
            Log.e(TAG, "Stop failed", e);
            if (recordingListener != null) recordingListener.onRecordingError(e.getMessage());
            return null;
        }
    }

    public Surface getRecorderSurface() { return mediaRecorder != null ? mediaRecorder.getSurface() : null; }
    public boolean isRecording() { return isRecording; }
    public boolean isPaused() { return isPaused; }
    public void setOnRecordingListener(OnRecordingListener listener) { this.recordingListener = listener; }

    public void release() {
        if (mediaRecorder != null) {
            try { if (isRecording) mediaRecorder.stop(); mediaRecorder.reset(); mediaRecorder.release(); }
            catch (Exception e) { Log.e(TAG, "Release failed", e); }
            mediaRecorder = null; isRecording = false; isPaused = false;
        }
    }
}