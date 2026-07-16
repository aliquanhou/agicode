package com.agicode.demo;

import android.app.Activity;
import android.os.Bundle;
import android.widget.TextView;
import android.graphics.Color;
import android.view.Gravity;
import android.widget.LinearLayout;
import android.widget.Button;
import android.view.View;
import android.content.Intent;
import android.net.Uri;

public class MainActivity extends Activity {

    private int clickCount = 0;
    private TextView statusText;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // 创建布局
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER);
        root.setBackgroundColor(Color.parseColor("#1a1a2e"));
        root.setPadding(40, 40, 40, 40);

        // 标题
        TextView title = new TextView(this);
        title.setText("🚀 AgiCode");
        title.setTextSize(36);
        title.setTextColor(Color.parseColor("#e94560"));
        title.setGravity(Gravity.CENTER);
        title.setPadding(0, 60, 0, 20);

        // 副标题
        TextView subtitle = new TextView(this);
        subtitle.setText("全功能自主 AI 工程智能体");
        subtitle.setTextSize(18);
        subtitle.setTextColor(Color.parseColor("#0f3460"));
        subtitle.setGravity(Gravity.CENTER);
        subtitle.setPadding(0, 0, 0, 40);

        // 状态文字
        statusText = new TextView(this);
        statusText.setText("🔥 APK 构建成功！\n由 AgiCode 自动生成");
        statusText.setTextSize(16);
        statusText.setTextColor(Color.parseColor("#16213e"));
        statusText.setGravity(Gravity.CENTER);
        statusText.setPadding(30, 30, 30, 30);
        statusText.setBackgroundColor(Color.parseColor("#e94560"));
        statusText.setPadding(20, 20, 20, 20);

        // 点击按钮
        Button clickBtn = new Button(this);
        clickBtn.setText("点击我！");
        clickBtn.setTextSize(16);
        clickBtn.setBackgroundColor(Color.parseColor("#0f3460"));
        clickBtn.setTextColor(Color.WHITE);
        clickBtn.setPadding(30, 15, 30, 15);
        clickBtn.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                clickCount++;
                statusText.setText("已点击 " + clickCount + " 次！\nAgiCode 无所不能！🔥");
            }
        });

        // 打开 GitHub 按钮
        Button githubBtn = new Button(this);
        githubBtn.setText("🌐 访问 AgiCode");
        githubBtn.setTextSize(14);
        githubBtn.setBackgroundColor(Color.parseColor("#16213e"));
        githubBtn.setTextColor(Color.WHITE);
        githubBtn.setPadding(30, 15, 30, 15);
        githubBtn.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                statusText.setText("正在打开浏览器...");
            }
        });

        // 组装布局
        root.addView(title);
        root.addView(subtitle);
        root.addView(statusText);
        root.addView(clickBtn);
        root.addView(githubBtn);

        setContentView(root);
    }
}
