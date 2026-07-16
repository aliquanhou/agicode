import os

drawable_dir = 'app/src/main/res/drawable'

drawables = {
    'bg_grid.xml': '''<?xml version="1.0" encoding="utf-8"?>
<layer-list xmlns:android="http://schemas.android.com/apk/res/android">
    <item>
        <shape android:shape="rectangle">
            <solid android:color="#00000000"/>
        </shape>
    </item>
    <!-- 垂直线 -->
    <item android:top="0dp" android:bottom="0dp" android:left="33.33%" android:right="66.66%">
        <shape android:shape="rectangle">
            <stroke android:width="1dp" android:color="#44FFFFFF"/>
        </shape>
    </item>
    <!-- 水平线 -->
    <item android:left="0dp" android:right="0dp" android:top="33.33%" android:bottom="66.66%">
        <shape android:shape="rectangle">
            <stroke android:width="1dp" android:color="#44FFFFFF"/>
        </shape>
    </item>
</layer-list>''',

    'bg_level.xml': '''<?xml version="1.0" encoding="utf-8"?>
<layer-list xmlns:android="http://schemas.android.com/apk/res/android">
    <item>
        <shape android:shape="rectangle">
            <solid android:color="#00000000"/>
        </shape>
    </item>
    <!-- 十字线 -->
    <item android:top="49%" android:bottom="49%" android:left="10%" android:right="10%">
        <shape android:shape="rectangle">
            <stroke android:width="1dp" android:color="#44FF4444"/>
        </shape>
    </item>
    <item android:left="49%" android:right="49%" android:top="10%" android:bottom="10%">
        <shape android:shape="rectangle">
            <stroke android:width="1dp" android:color="#44FF4444"/>
        </shape>
    </item>
</layer-list>''',

    'bg_slider_thumb.xml': '''<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="oval">
    <solid android:color="#FFD700"/>
    <stroke android:width="2dp" android:color="#FFFFFF"/>
    <size android:width="16dp" android:height="16dp"/>
</shape>''',

    'bg_slider_progress.xml': '''<?xml version="1.0" encoding="utf-8"?>
<layer-list xmlns:android="http://schemas.android.com/apk/res/android">
    <item android:id="@android:id/background">
        <shape android:shape="rectangle">
            <solid android:color="#33FFFFFF"/>
            <corners android:radius="2dp"/>
        </shape>
    </item>
    <item android:id="@android:id/progress">
        <shape android:shape="rectangle">
            <solid android:color="#FFD700"/>
            <corners android:radius="2dp"/>
        </shape>
    </item>
</layer-list>''',

    'bg_scene_btn.xml': '''<?xml version="1.0" encoding="utf-8"?>
<selector xmlns:android="http://schemas.android.com/apk/res/android">
    <item android:state_selected="true">
        <shape android:shape="rectangle">
            <solid android:color="#FFD700"/>
            <corners android:radius="16dp"/>
        </shape>
    </item>
    <item>
        <shape android:shape="rectangle">
            <solid android:color="#33FFFFFF"/>
            <corners android:radius="16dp"/>
        </shape>
    </item>
</selector>''',

    'bg_shutter_ring.xml': '''<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="oval">
    <solid android:color="#00000000"/>
    <stroke android:width="3dp" android:color="#FFFFFF"/>
    <size android:width="80dp" android:height="80dp"/>
</shape>''',

    'bg_shutter.xml': '''<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="oval">
    <solid android:color="#FFFFFF"/>
    <size android:width="64dp" android:height="64dp"/>
</shape>''',

    'bg_pro_active.xml': '''<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <solid android:color="#FFD700"/>
    <corners android:radius="12dp"/>
    <padding android:left="8dp" android:right="8dp" android:top="2dp" android:bottom="2dp"/>
</shape>''',

    'ic_flash_on.xml': '''<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="24dp" android:height="24dp" android:viewportWidth="24" android:viewportHeight="24">
    <path android:fillColor="#FFFFFF" android:pathData="M7,2v11h3v9l7,-12h-4l4,-8z"/>
</vector>''',

    'ic_flash_off.xml': '''<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="24dp" android:height="24dp" android:viewportWidth="24" android:viewportHeight="24">
    <path android:fillColor="#FFFFFF" android:pathData="M3.27,3L2,4.27l5,5V13h3v9l3.58,-6.14L17.73,20L19,18.73L3.27,3zM17,10h-4l4,-8H7v2.18l8.46,8.46L17,10z"/>
</vector>''',

    'ic_grid.xml': '''<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="24dp" android:height="24dp" android:viewportWidth="24" android:viewportHeight="24">
    <path android:fillColor="#FFFFFF" android:pathData="M10,4h4v4h-4zM4,16h4v4H4zM4,10h4v4H4zM10,16h4v4h-4zM16,4h4v4h-4zM16,10h4v4h-4zM16,16h4v4h-4zM10,10h4v4h-4z"/>
</vector>''',

    'ic_mode_video.xml': '''<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="24dp" android:height="24dp" android:viewportWidth="24" android:viewportHeight="24">
    <path android:fillColor="#FFFFFF" android:pathData="M17,10.5V7c0,-0.55 -0.45,-1 -1,-1H4c-0.55,0 -1,0.45 -1,1v10c0,0.55 0.45,1 1,1h12c0.55,0 1,-0.45 1,-1v-3.5l4,4v-11l-4,4z"/>
</vector>''',

    'ic_focus_success.xml': '''<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="48dp" android:height="48dp" android:viewportWidth="48" android:viewportHeight="48">
    <path android:fillColor="#00FF00" android:pathData="M24,4L24,12M24,36L24,44M4,24L12,24M36,24L44,24"/>
    <path android:fillColor="#00FF00" android:pathData="M18,24l4,4l8,-8" android:strokeWidth="3" android:strokeColor="#00FF00"/>
</vector>''',

    'ic_focus_fail.xml': '''<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="48dp" android:height="48dp" android:viewportWidth="48" android:viewportHeight="48">
    <path android:fillColor="#FF0000" android:pathData="M24,4L24,12M24,36L24,44M4,24L12,24M36,24L44,24"/>
    <path android:fillColor="#FF0000" android:pathData="M18,18l12,12M30,18l-12,12" android:strokeWidth="3" android:strokeColor="#FF0000"/>
</vector>'''
}

for name, content in drawables.items():
    path = os.path.join(drawable_dir, name)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'Created: {name}')

print('All drawables created!')
