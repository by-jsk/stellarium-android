// SPDX-License-Identifier: GPL-2.0-or-later
// Copyright (C) 2026 by-jsk
package org.byjsk.stellartouch;

import org.qtproject.qt.android.bindings.QtActivity;
import android.app.DownloadManager;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.content.pm.Signature;
import android.database.Cursor;
import android.net.Uri;
import android.os.Bundle;
import android.os.Environment;
import android.os.Handler;
import android.provider.Settings;
import android.widget.Toast;
import android.view.View;
import android.view.WindowManager;
import android.graphics.Color;
import java.io.File;
import java.util.Arrays;
import java.util.Locale;
import org.json.JSONObject;

/** System download + package installer, preserving the installed package and its data. */
public class StellarActivity extends QtActivity {
    // Only tools/prepare.py enables this in the x86 CI fixture. ARM64 distribution forbids HTTP.
    private static final boolean CI_FIXTURE = false;
    private final Handler handler = new Handler();
    private SharedPreferences state;
    private boolean polling;

    public boolean isSmokeTest() { return getIntent().getBooleanExtra("stellarSmokeTest", false); }
    public boolean isUpgradeTest() { return CI_FIXTURE && getIntent().getBooleanExtra("stellarUpgradeTest", false); }
    public int installedVersionCode() {
        try { return (int)getPackageManager().getPackageInfo(getPackageName(),0).getLongVersionCode(); }
        catch(Exception e) { return Integer.MAX_VALUE; }
    }
    public String countryName(String country, String language) {
        return new Locale("",country).getDisplayCountry(Locale.forLanguageTag(language));
    }
    private String text(String key) {
        try { return new JSONObject(state.getString("messages","{}")).optString(key,"Stellar Touch"); }
        catch(Exception e) { return "Stellar Touch"; }
    }
    private void message(String key) { Toast.makeText(this,text(key),Toast.LENGTH_LONG).show(); }
    public void setNightLighting(boolean enabled, int brightness, boolean keepAwake) {
        runOnUiThread(() -> {
            WindowManager.LayoutParams attributes=getWindow().getAttributes();
            attributes.screenBrightness=enabled ? 0.02f+0.18f*Math.max(5,Math.min(brightness,100))/100.0f : WindowManager.LayoutParams.BRIGHTNESS_OVERRIDE_NONE;
            getWindow().setAttributes(attributes);
            getWindow().setStatusBarColor(Color.BLACK);getWindow().setNavigationBarColor(Color.BLACK);
            if(keepAwake)getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
            else getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
            getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY | View.SYSTEM_UI_FLAG_FULLSCREEN | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_LAYOUT_STABLE);
        });
    }

    @Override public void onCreate(Bundle saved) {
        android.util.Log.i("StellarTouch", "STELLAR_BOOT Activity create");
        super.onCreate(saved);
        state = getSharedPreferences("updates", MODE_PRIVATE);
        setNightLighting(true,40,true); // Dark launch until the native saved preference is loaded.
        android.util.Log.i("StellarTouch", "STELLAR_BOOT Activity created");
    }

    /** Called only after the user taps the localized install button. */
    public void downloadUpdate(final String url, final int code, final String messages) {
        runOnUiThread(() -> {
            boolean fixtureUrl = CI_FIXTURE && url.equals("http://10.0.2.2:8765/StellarTouch-v0.1.0.apk");
            if (!fixtureUrl && !url.matches("https://github\\.com/by-jsk/app-downloads/releases/download/stellar-touch-v([0-9]+\\.[0-9]+\\.[0-9]+)/StellarTouch-v\\1\\.apk")) return;
            try {
                if (code <= getPackageManager().getPackageInfo(getPackageName(), 0).getLongVersionCode()) return;
                if (state.getLong("download", -1) >= 0) { poll(); return; }
                state.edit().putString("url", url).putInt("code", code).putString("messages", messages).apply();
                if (!getPackageManager().canRequestPackageInstalls()) {
                    message("allowInstall");
                    startActivity(new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:" + getPackageName())));
                    return;
                }
                enqueue();
            } catch (Exception e) { message("updateError"); android.util.Log.e("StellarTouch", "Update could not start", e); }
        });
    }

    private void enqueue() {
        String url = state.getString("url", "");
        if (url.isEmpty() || state.getLong("download", -1) >= 0) return;
        try {
            File directory = getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS);
            File destination = new File(directory, "StellarTouch-" + state.getInt("code", 0) + ".apk");
            if (destination.exists() && !destination.delete()) return;
            DownloadManager.Request request = new DownloadManager.Request(Uri.parse(url));
            request.setTitle(text("update"));
            request.setMimeType("application/vnd.android.package-archive");
            request.setDestinationUri(Uri.fromFile(destination));
            request.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
            long id = ((DownloadManager)getSystemService(Context.DOWNLOAD_SERVICE)).enqueue(request);
            state.edit().putLong("download", id).putString("path", destination.getAbsolutePath()).remove("url").apply();
            message("downloading");
            poll();
        } catch (Exception e) { message("updateError"); android.util.Log.e("StellarTouch", "Update download failed", e); }
    }

    private boolean sameSigner(PackageInfo installed, PackageInfo incoming) {
        if (installed.signingInfo == null || incoming.signingInfo == null) return false;
        Signature[] current = installed.signingInfo.getApkContentsSigners();
        Signature[] next = incoming.signingInfo.getApkContentsSigners();
        return Arrays.equals(current, next);
    }

    private void poll() {
        if (polling || state == null || state.getLong("download", -1) < 0) return;
        polling = true;
        handler.postDelayed(() -> {
            polling = false;
            long id = state.getLong("download", -1);
            if (id < 0) return;
            DownloadManager dm = (DownloadManager)getSystemService(Context.DOWNLOAD_SERVICE);
            try (Cursor cursor = dm.query(new DownloadManager.Query().setFilterById(id))) {
                if (cursor == null || !cursor.moveToFirst()) { state.edit().remove("download").apply(); return; }
                int status = cursor.getInt(cursor.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS));
                if (status == DownloadManager.STATUS_FAILED) {
                    state.edit().remove("download").apply(); message("updateError"); return;
                }
                if (status != DownloadManager.STATUS_SUCCESSFUL) { poll(); return; }
                PackageManager pm = getPackageManager();
                PackageInfo next = pm.getPackageArchiveInfo(state.getString("path", ""), PackageManager.GET_SIGNING_CERTIFICATES);
                PackageInfo installed = pm.getPackageInfo(getPackageName(), PackageManager.GET_SIGNING_CERTIFICATES);
                boolean valid = next != null && getPackageName().equals(next.packageName)
                    && next.getLongVersionCode() == state.getInt("code", 0)
                    && next.getLongVersionCode() > installed.getLongVersionCode()
                    && sameSigner(installed, next);
                state.edit().remove("download").apply();
                if (!valid) { message("updateError"); android.util.Log.e("StellarTouch", "Rejected APK package, version, or signer mismatch"); return; }
                Uri apk = dm.getUriForDownloadedFile(id);
                if (apk != null) startActivity(new Intent(Intent.ACTION_VIEW).setDataAndType(apk, "application/vnd.android.package-archive")
                    .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION));
            } catch (Exception e) { state.edit().remove("download").apply(); android.util.Log.e("StellarTouch", "Update install failed", e); }
        }, 750);
    }

    @Override protected void onResume() {
        super.onResume();
        if (state == null) return;
        if (getPackageManager().canRequestPackageInstalls()) enqueue();
        poll();
    }
    @Override protected void onDestroy() { handler.removeCallbacksAndMessages(null); super.onDestroy(); }
}
