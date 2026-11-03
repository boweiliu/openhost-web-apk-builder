package in.bowei.webapps.shell;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.PopupMenu;
import android.view.Gravity;
import android.view.ViewGroup;
import org.json.JSONObject;
import org.mozilla.geckoview.*;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;

/** A separate Android app and private Firefox profile for one website. */
public final class MainActivity extends Activity {
    private static GeckoRuntime runtime;
    private GeckoSession session;
    private GeckoView view;
    private TextView origin;
    private boolean canGoBack;
    private String startUrl;
    private String currentUrl;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        try {
            ByteArrayOutputStream configBytes = new ByteArrayOutputStream();
            try (InputStream input = getAssets().open("site.json")) {
                byte[] buffer = new byte[4096]; int count;
                while ((count = input.read(buffer)) != -1) configBytes.write(buffer, 0, count);
            }
            JSONObject config = new JSONObject(configBytes.toString("UTF-8"));
            startUrl = config.getString("url");
            currentUrl = startUrl;
            setTitle(config.getString("name"));
            if (runtime == null) {
                // Gecko supports a private app-owned YAML configuration. Do not
                // expose a release app's debugging interface or Google FIDO API.
                File prefs = new File(getFilesDir(), "runtime.yaml");
                try (FileOutputStream out = new FileOutputStream(prefs)) {
                    out.write(("prefs:\n  security.webauth.webauthn: false\n").getBytes(StandardCharsets.UTF_8));
                }
                runtime = GeckoRuntime.create(this, new GeckoRuntimeSettings.Builder()
                    .configFilePath(prefs.getAbsolutePath())
                    .remoteDebuggingEnabled(false).build());
            }
            LinearLayout root = new LinearLayout(this);
            root.setOrientation(LinearLayout.VERTICAL);
            root.setFitsSystemWindows(true);
            origin = new TextView(this);
            origin.setTextSize(12);
            origin.setTextColor(0xff445065);
            origin.setBackgroundColor(0xfff1f4f8);
            origin.setGravity(Gravity.CENTER_VERTICAL);
            origin.setPadding(24, 6, 24, 6);
            origin.setText(Uri.parse(startUrl).getHost() + "   ·   Menu");
            origin.setOnClickListener(v -> showMenu());
            int barHeight = (int) (40 * getResources().getDisplayMetrics().density);
            root.addView(origin, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, barHeight));
            view = new GeckoView(this);
            root.addView(view, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1));
            setContentView(root);
            session = makeSession();
            session.open(runtime);
            view.setSession(session);
            session.loadUri(startUrl);
        } catch (Exception error) {
            new AlertDialog.Builder(this).setTitle("Unable to open app")
                .setMessage(error.toString()).setPositiveButton("Close", (d,w) -> finish()).show();
        }
    }

    private GeckoSession makeSession() {
        GeckoSession result = new GeckoSession();
        result.setContentDelegate(new GeckoSession.ContentDelegate() {});
        result.setNavigationDelegate(new GeckoSession.NavigationDelegate() {
            @Override public void onLocationChange(GeckoSession s, String url, java.util.List<GeckoSession.PermissionDelegate.ContentPermission> permissions, Boolean gesture) {
                currentUrl = url;
                origin.setText(Uri.parse(url).getHost() + "   ·   Menu");
            }
            @Override public void onCanGoBack(GeckoSession s, boolean back) { canGoBack = back; }
            @Override public GeckoResult<AllowOrDeny> onLoadRequest(GeckoSession s, LoadRequest request) {
                String scheme = Uri.parse(request.uri).getScheme();
                return GeckoResult.fromValue("https".equals(scheme) || "about".equals(scheme) ? AllowOrDeny.ALLOW : AllowOrDeny.DENY);
            }
            @Override public GeckoResult<GeckoSession> onNewSession(GeckoSession s, String uri) {
                // Keep a requested login popup in this app's existing profile.
                s.loadUri(uri);
                return GeckoResult.fromValue(null);
            }
        });
        result.setPromptDelegate(new GeckoSession.PromptDelegate() {
            @Override public GeckoResult<PromptResponse> onAlertPrompt(GeckoSession s, AlertPrompt p) {
                GeckoResult<PromptResponse> r = new GeckoResult<>();
                new AlertDialog.Builder(MainActivity.this).setTitle(p.title).setMessage(p.message)
                    .setPositiveButton("OK", (d,w) -> r.complete(p.dismiss()))
                    .setOnCancelListener(d -> r.complete(p.dismiss())).show();
                return r;
            }
            @Override public GeckoResult<PromptResponse> onTextPrompt(GeckoSession s, TextPrompt p) {
                GeckoResult<PromptResponse> r = new GeckoResult<>();
                EditText input = new EditText(MainActivity.this); input.setText(p.defaultValue);
                new AlertDialog.Builder(MainActivity.this).setTitle(p.title).setMessage(p.message).setView(input)
                    .setPositiveButton("OK", (d,w) -> r.complete(p.confirm(input.getText().toString())))
                    .setNegativeButton("Cancel", (d,w) -> r.complete(p.dismiss()))
                    .setOnCancelListener(d -> r.complete(p.dismiss())).show();
                return r;
            }
            @Override public GeckoResult<PromptResponse> onButtonPrompt(GeckoSession s, ButtonPrompt p) {
                GeckoResult<PromptResponse> r = new GeckoResult<>();
                new AlertDialog.Builder(MainActivity.this).setTitle(p.title).setMessage(p.message)
                    .setPositiveButton("OK", (d,w) -> r.complete(p.confirm(ButtonPrompt.Type.POSITIVE)))
                    .setNegativeButton("Cancel", (d,w) -> r.complete(p.confirm(ButtonPrompt.Type.NEGATIVE)))
                    .setOnCancelListener(d -> r.complete(p.dismiss())).show();
                return r;
            }
            @Override public GeckoResult<PromptResponse> onAuthPrompt(GeckoSession s, AuthPrompt p) {
                GeckoResult<PromptResponse> r = new GeckoResult<>();
                LinearLayout fields = new LinearLayout(MainActivity.this); fields.setOrientation(LinearLayout.VERTICAL);
                EditText username = new EditText(MainActivity.this); username.setHint("Username"); fields.addView(username);
                EditText password = new EditText(MainActivity.this); password.setHint("Password"); password.setInputType(129); fields.addView(password);
                new AlertDialog.Builder(MainActivity.this).setTitle("Sign in").setMessage(p.authOptions.uri).setView(fields)
                    .setPositiveButton("Sign in", (d,w) -> r.complete(p.confirm(username.getText().toString(), password.getText().toString())))
                    .setNegativeButton("Cancel", (d,w) -> r.complete(p.dismiss()))
                    .setOnCancelListener(d -> r.complete(p.dismiss())).show();
                return r;
            }
        });
        return result;
    }

    private void showMenu() {
        PopupMenu menu = new PopupMenu(this, origin);
        menu.getMenu().add("Reload").setOnMenuItemClickListener(i -> { session.reload(); return true; });
        menu.getMenu().add("Home").setOnMenuItemClickListener(i -> { session.loadUri(startUrl); return true; });
        menu.getMenu().add("Open in browser").setOnMenuItemClickListener(i -> {
            startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(currentUrl))); return true;
        });
        menu.getMenu().add("About this app").setOnMenuItemClickListener(i -> {
            new AlertDialog.Builder(this).setTitle(getTitle()).setMessage("Firefox GeckoView 159\n\nSource: " + startUrl +
                "\n\nSeparate browser storage. Background push, passkeys, Firefox Sync, and extensions are not included in this first version.")
                .setPositiveButton("OK", null).show(); return true;
        });
        menu.show();
    }

    @Override public void onBackPressed() {
        if (session != null && canGoBack) session.goBack(); else super.onBackPressed();
    }
    @Override protected void onStart() { super.onStart(); if (session != null) session.setActive(true); }
    @Override protected void onStop() { if (session != null) session.setActive(false); super.onStop(); }
    @Override protected void onDestroy() { if (session != null) session.close(); super.onDestroy(); }
}
