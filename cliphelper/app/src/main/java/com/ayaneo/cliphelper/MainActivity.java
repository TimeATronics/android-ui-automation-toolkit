package com.ayaneo.cliphelper;

import android.app.Activity;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.os.Bundle;
import android.util.Base64;

import java.nio.charset.StandardCharsets;

/**
 * Sets the clipboard from a base64-encoded intent extra, then closes itself.
 *
 * This exists because some controller-first Android UIs use a custom on-screen
 * keyboard that does not reliably type spaces, capitals, or punctuation when
 * driven through ADB. Pasting from the system clipboard avoids that path.
 *
 * Usage:
 *   adb shell am start -n com.ayaneo.cliphelper/.MainActivity --es b64 <base64>
 *
 * The base64 value must encode UTF-8 text. The activity is transparent and
 * finishes immediately after writing the clipboard.
 */
public final class MainActivity extends Activity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        final String encoded = getIntent().getStringExtra("b64");
        String text = "";
        if (encoded != null) {
            try {
                text = new String(
                        Base64.decode(encoded, Base64.DEFAULT),
                        StandardCharsets.UTF_8);
            } catch (IllegalArgumentException ignored) {
                // Leave the clipboard empty rather than crashing.
            }
        }

        final ClipboardManager clipboard =
                (ClipboardManager) getSystemService(CLIPBOARD_SERVICE);
        if (clipboard != null) {
            clipboard.setPrimaryClip(ClipData.newPlainText("Clipboard bridge", text));
        }

        finish();
    }
}
