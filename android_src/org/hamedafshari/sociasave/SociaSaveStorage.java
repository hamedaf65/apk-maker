package org.hamedafshari.sociasave;

import android.app.Activity;
import android.content.ContentValues;
import android.content.Intent;
import android.database.Cursor;
import android.graphics.Color;
import android.graphics.Insets;
import android.content.res.ColorStateList;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.provider.DocumentsContract;
import android.provider.MediaStore;
import android.webkit.CookieManager;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.webkit.WebResourceRequest;
import android.webkit.JavascriptInterface;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowInsets;
import android.widget.Button;
import android.widget.LinearLayout;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;

public final class SociaSaveStorage {
    private static WebView loginWebView;
    private static LinearLayout loginContainer;
    private static WebView facebookCaptureWebView;
    private static volatile String facebookCaptureStatus = "idle";
    private static volatile String facebookCaptureHtml = "";

    private SociaSaveStorage() {}

    public static String getInstagramCookies() {
        return getPlatformCookies("https://www.instagram.com");
    }

    public static String getPlatformCookies(String url) {
        CookieManager manager = CookieManager.getInstance();
        manager.setAcceptCookie(true);
        String value = manager.getCookie(url);
        manager.flush();
        return value == null ? "" : value;
    }

    public static void openInstagramLogin(final Activity activity) {
        openPlatformLogin(activity, "https://www.instagram.com/accounts/login/");
    }

    public static void openPlatformLogin(final Activity activity, final String loginUrl) {
        activity.runOnUiThread(() -> {
            closeInstagramLogin(activity);

            LinearLayout root = new LinearLayout(activity);
            root.setOrientation(LinearLayout.VERTICAL);
            root.setBackgroundColor(Color.rgb(250, 248, 255));

            LinearLayout toolbar = new LinearLayout(activity);
            toolbar.setOrientation(LinearLayout.HORIZONTAL);
            toolbar.setGravity(Gravity.CENTER_VERTICAL);
            toolbar.setPadding(12, 8, 12, 8);
            toolbar.setBackgroundColor(Color.rgb(245, 239, 255));

            Button back = new Button(activity);
            back.setText("Back");
            back.setAllCaps(false);
            back.setTextColor(Color.rgb(65, 35, 105));
            back.setBackgroundTintList(ColorStateList.valueOf(Color.rgb(235, 226, 250)));
            back.setMinHeight(52);
            back.setOnClickListener(v -> {
                if (loginWebView != null && loginWebView.canGoBack()) {
                    loginWebView.goBack();
                }
            });

            Button close = new Button(activity);
            close.setText("Close");
            close.setAllCaps(false);
            close.setTextColor(Color.WHITE);
            close.setBackgroundTintList(ColorStateList.valueOf(Color.rgb(112, 55, 205)));
            close.setMinHeight(52);
            close.setOnClickListener(v -> closeInstagramLogin(activity));

            LinearLayout.LayoutParams buttonParams =
                new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
            toolbar.addView(back, buttonParams);
            toolbar.addView(close, new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));

            WebView webView = new WebView(activity);
            WebSettings settings = webView.getSettings();
            settings.setJavaScriptEnabled(true);
            settings.setDomStorageEnabled(true);
            settings.setLoadsImagesAutomatically(true);
            CookieManager.getInstance().setAcceptCookie(true);
            webView.setWebViewClient(new WebViewClient());
            webView.setBackgroundColor(Color.WHITE);

            // Keep navigation controls anchored at the bottom of the login page.
            root.addView(webView, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));
            root.addView(toolbar, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(activity, 68)));

            root.setOnApplyWindowInsetsListener((view, insets) -> {
                int left;
                int top;
                int right;
                int bottom;
                if (Build.VERSION.SDK_INT >= 30) {
                    Insets bars = insets.getInsets(WindowInsets.Type.systemBars());
                    left = bars.left;
                    top = bars.top;
                    right = bars.right;
                    bottom = bars.bottom;
                } else {
                    left = insets.getSystemWindowInsetLeft();
                    top = insets.getSystemWindowInsetTop();
                    right = insets.getSystemWindowInsetRight();
                    bottom = insets.getSystemWindowInsetBottom();
                }
                view.setPadding(left, top, right, bottom);
                return insets;
            });

            activity.addContentView(root, new ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
            root.requestApplyInsets();

            loginContainer = root;
            loginWebView = webView;
            webView.loadUrl(loginUrl);
        });
    }

    public static void closeInstagramLogin(final Activity activity) {
        Runnable closeTask = () -> {
            try {
                if (loginWebView != null) {
                    loginWebView.stopLoading();
                    loginWebView.loadUrl("about:blank");
                    loginWebView.destroy();
                    loginWebView = null;
                }
                if (loginContainer != null) {
                    ViewGroup parent = (ViewGroup) loginContainer.getParent();
                    if (parent != null) parent.removeView(loginContainer);
                    loginContainer = null;
                }
            } catch (Exception ignored) {
                loginWebView = null;
                loginContainer = null;
            }
        };
        if (activity != null) activity.runOnUiThread(closeTask);
        else closeTask.run();
    }

    public static boolean isInstagramLoginVisible() {
        return loginContainer != null;
    }

    public static boolean ensureSociaSaveFolder(Activity activity) throws IOException {
        if (Build.VERSION.SDK_INT < 29) {
            throw new IOException("SociaSave public folder requires Android 10 or newer.");
        }
        ContentValues values = new ContentValues();
        values.put(MediaStore.MediaColumns.DISPLAY_NAME, ".nomedia");
        values.put(MediaStore.MediaColumns.MIME_TYPE, "application/octet-stream");
        values.put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS + "/SociaSave/");
        Uri uri = activity.getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values);
        if (uri == null) throw new IOException("Android could not initialize Download/SociaSave.");
        try (OutputStream output = activity.getContentResolver().openOutputStream(uri, "w")) {
            if (output == null) throw new IOException("Could not initialize SociaSave folder.");
        }
        return true;
    }

    public static boolean exportDirectory(Activity activity, String sourceDirectory,
                                          String relativeDirectory) throws IOException {
        if (Build.VERSION.SDK_INT < 29) {
            throw new IOException("Public Downloads export requires Android 10 or newer.");
        }
        int exported = exportTree(activity, new File(sourceDirectory), relativeDirectory);
        if (exported == 0) throw new IOException("No downloadable media or caption files were found.");
        return true;
    }

    private static int exportTree(Activity activity, File folder, String relativeDirectory)
        throws IOException {
        File[] entries = folder.listFiles();
        if (entries == null) throw new IOException("Downloaded folder could not be read: " + folder);
        int exported = 0;
        for (File entry : entries) {
            if (entry.isDirectory()) {
                exported += exportTree(activity, entry, relativeDirectory + "/" + entry.getName());
                continue;
            }
            if (!entry.isFile()) continue;
            String lower = entry.getName().toLowerCase();
            if (lower.endsWith(".json") || lower.endsWith(".part") || lower.startsWith(".")) continue;
            exportOne(activity, entry, relativeDirectory);
            exported++;
        }
        return exported;
    }


    // A separate, non-interactive WebView used only to inspect publicly accessible
    // Facebook page markup. It never attempts to defeat login or privacy controls.
    public static boolean startFacebookPageCapture(final Activity activity, final String pageUrl) {
        if (activity == null || !isAllowedFacebookPage(pageUrl)) return false;
        activity.runOnUiThread(() -> {
            stopFacebookPageCapture(activity);
            facebookCaptureStatus = "loading";
            facebookCaptureHtml = "";

            WebView view = new WebView(activity);
            WebSettings settings = view.getSettings();
            settings.setJavaScriptEnabled(true);
            settings.setDomStorageEnabled(true);
            settings.setLoadsImagesAutomatically(false);
            settings.setBlockNetworkImage(true);
            settings.setSupportMultipleWindows(false);
            CookieManager cookies = CookieManager.getInstance();
            cookies.setAcceptCookie(true);

            view.addJavascriptInterface(new FacebookCaptureBridge(), "SociaSaveCapture");
            view.setWebViewClient(new WebViewClient() {
                @Override
                public boolean shouldOverrideUrlLoading(WebView webView, String url) {
                    return !isAllowedFacebookPage(url);
                }

                @Override
                public boolean shouldOverrideUrlLoading(WebView webView, WebResourceRequest request) {
                    return !isAllowedFacebookPage(request.getUrl().toString());
                }

                @Override
                public void onPageFinished(WebView webView, String url) {
                    super.onPageFinished(webView, url);
                    if (!isAllowedFacebookPage(url) || facebookCaptureWebView != webView) {
                        facebookCaptureStatus = "error";
                        return;
                    }
                    String script =
                        "(function(){try{" +
                        "var started=Date.now(),last=Date.now();" +
                        "var observer=new MutationObserver(function(){last=Date.now();});" +
                        "observer.observe(document.documentElement,{childList:true,subtree:true});" +
                        "var timer=setInterval(function(){" +
                        "if(Date.now()-started>16000){clearInterval(timer);observer.disconnect();" +
                        "window.SociaSaveCapture.onError('Facebook page did not stabilize in time');return;}" +
                        "if(document.readyState==='complete'&&Date.now()-last>1300){" +
                        "clearInterval(timer);observer.disconnect();" +
                        "var value=document.documentElement?document.documentElement.outerHTML:'';" +
                        "if(value.length>1800000)value=value.substring(0,1800000);" +
                        "window.SociaSaveCapture.onCapture(value);" +
                        "}},400);" +
                        "}catch(e){window.SociaSaveCapture.onError(String(e));}})();";
                    webView.evaluateJavascript(script, null);
                }
            });

            // Keep the WebView attached so Android continues loading it, but
            // effectively invisible and outside the user's touch area.
            view.setAlpha(0.01f);
            view.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS);
            activity.addContentView(view, new ViewGroup.LayoutParams(1, 1));
            facebookCaptureWebView = view;
            view.loadUrl(pageUrl);
        });
        return true;
    }

    public static String getFacebookPageCaptureStatus() {
        return facebookCaptureStatus;
    }

    public static String getFacebookPageCaptureHtml() {
        return facebookCaptureHtml;
    }

    public static void stopFacebookPageCapture(final Activity activity) {
        Runnable stopTask = () -> {
            try {
                if (facebookCaptureWebView != null) {
                    ViewGroup parent = (ViewGroup) facebookCaptureWebView.getParent();
                    facebookCaptureWebView.stopLoading();
                    facebookCaptureWebView.removeJavascriptInterface("SociaSaveCapture");
                    facebookCaptureWebView.loadUrl("about:blank");
                    facebookCaptureWebView.destroy();
                    if (parent != null) parent.removeView(facebookCaptureWebView);
                }
            } catch (Exception ignored) {}
            facebookCaptureWebView = null;
        };
        if (activity != null) activity.runOnUiThread(stopTask);
        else stopTask.run();
    }

    private static boolean isAllowedFacebookPage(String value) {
        try {
            Uri uri = Uri.parse(value);
            String host = uri.getHost();
            if (host == null || !"https".equalsIgnoreCase(uri.getScheme())) return false;
            host = host.toLowerCase();
            return host.equals("facebook.com") || host.endsWith(".facebook.com")
                || host.equals("fb.com") || host.endsWith(".fb.com")
                || host.equals("fb.watch");
        } catch (Exception ignored) {
            return false;
        }
    }

    private static final class FacebookCaptureBridge {
        @JavascriptInterface
        public void onCapture(String html) {
            facebookCaptureHtml = html == null ? "" : html;
            facebookCaptureStatus = facebookCaptureHtml.isEmpty() ? "error" : "done";
        }

        @JavascriptInterface
        public void onError(String message) {
            facebookCaptureHtml = "";
            facebookCaptureStatus = "error";
        }
    }

    private static int dp(Activity activity, int value) {
        return (int) (value * activity.getResources().getDisplayMetrics().density + 0.5f);
    }

    private static void exportOne(Activity activity, File source, String relativeDirectory)
        throws IOException {
        String mime = mimeType(source.getName());
        String safeRelative = relativeDirectory.replace("\\", "/");
        while (safeRelative.startsWith("/")) safeRelative = safeRelative.substring(1);
        while (safeRelative.endsWith("/")) safeRelative = safeRelative.substring(0, safeRelative.length() - 1);

        ContentValues values = new ContentValues();
        values.put(MediaStore.MediaColumns.DISPLAY_NAME, source.getName());
        values.put(MediaStore.MediaColumns.MIME_TYPE, mime);
        values.put(MediaStore.MediaColumns.RELATIVE_PATH,
            Environment.DIRECTORY_DOWNLOADS + "/SociaSave/" + safeRelative + "/");
        values.put(MediaStore.MediaColumns.IS_PENDING, 1);

        Uri collection = MediaStore.Downloads.EXTERNAL_CONTENT_URI;
        Uri destination = activity.getContentResolver().insert(collection, values);
        if (destination == null) throw new IOException("Android could not create a public download entry.");

        try (InputStream input = new FileInputStream(source);
             OutputStream output = activity.getContentResolver().openOutputStream(destination, "w")) {
            if (output == null) throw new IOException("Android could not open the destination file.");
            byte[] buffer = new byte[64 * 1024];
            int count;
            while ((count = input.read(buffer)) != -1) {
                output.write(buffer, 0, count);
            }
            output.flush();
            ContentValues completed = new ContentValues();
            completed.put(MediaStore.MediaColumns.IS_PENDING, 0);
            activity.getContentResolver().update(destination, completed, null, null);
        } catch (Exception error) {
            activity.getContentResolver().delete(destination, null, null);
            if (error instanceof IOException) throw (IOException) error;
            throw new IOException("Could not copy " + source.getName() + " to Downloads.", error);
        }
    }

    private static String mimeType(String name) {
        String lower = name.toLowerCase();
        if (lower.endsWith(".jpg") || lower.endsWith(".jpeg")) return "image/jpeg";
        if (lower.endsWith(".png")) return "image/png";
        if (lower.endsWith(".webp")) return "image/webp";
        if (lower.endsWith(".gif")) return "image/gif";
        if (lower.endsWith(".mp4") || lower.endsWith(".m4v")) return "video/mp4";
        if (lower.endsWith(".mov")) return "video/quicktime";
        if (lower.endsWith(".webm")) return "video/webm";
        if (lower.endsWith(".mkv")) return "video/x-matroska";
        if (lower.endsWith(".mp3")) return "audio/mpeg";
        if (lower.endsWith(".m4a")) return "audio/mp4";
        if (lower.endsWith(".txt")) return "text/plain";
        return "application/octet-stream";
    }

    public static boolean openSociaSaveFolder(final Activity activity) {
        if (activity == null) return false;
        final String authority = "com.android.externalstorage.documents";
        Uri folderUri = DocumentsContract.buildDocumentUri(
            authority, "primary:Download/SociaSave");

        Intent view = new Intent(Intent.ACTION_VIEW);
        view.setDataAndType(folderUri, "vnd.android.document/directory");
        view.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
        try {
            if (view.resolveActivity(activity.getPackageManager()) != null) {
                activity.startActivity(view);
                return true;
            }
        } catch (Exception ignored) {}

        try {
            Intent picker = new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE);
            if (Build.VERSION.SDK_INT >= 26) {
                picker.putExtra(DocumentsContract.EXTRA_INITIAL_URI, folderUri);
            }
            picker.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION |
                Intent.FLAG_GRANT_WRITE_URI_PERMISSION |
                Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
            activity.startActivity(picker);
            return true;
        } catch (Exception ignored) {
            return false;
        }
    }
}
