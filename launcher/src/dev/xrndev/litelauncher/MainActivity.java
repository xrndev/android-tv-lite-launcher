package dev.xrndev.litelauncher;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.DialogInterface;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.graphics.Bitmap;
import android.graphics.BitmapShader;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.Shader;
import android.graphics.drawable.BitmapDrawable;
import android.graphics.drawable.ColorDrawable;
import android.graphics.drawable.Drawable;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.AdapterView;
import android.widget.BaseAdapter;
import android.widget.GridView;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.Comparator;
import java.util.Date;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * Launcher minimo para Android TV con poca RAM: una GridView, sin animaciones,
 * sin dependencias. El orden y las apps ocultas se guardan en SharedPreferences
 * y se cambian con una pulsacion larga sobre una app.
 */
public class MainActivity extends Activity
        implements AdapterView.OnItemClickListener, AdapterView.OnItemLongClickListener {

    /** Orden inicial; luego manda el que el usuario guarde desde el menu. */
    private static final String[] DEFAULT_ORDER = {
        "com.android.vending",
        "com.google.android.youtube.tv",
        "com.stremio.one",
        "com.android.tv.settings",
    };
    /** Entradas tecnicas que nunca se muestran. */
    private static final String[] ALWAYS_HIDDEN = {
        "com.tcl.tcl_bt_rcu_service",
    };
    private static final int COLUMNS = 5;
    private static final String PREFS = "lite";
    private static final String KEY_ORDER = "order";
    private static final String KEY_HIDDEN = "hidden";

    private static final int ACT_LEFT = 0;
    private static final int ACT_RIGHT = 1;
    private static final int ACT_HIDE = 2;
    private static final int ACT_INFO = 3;
    private static final int ACT_RESTORE = 4;

    private static class Entry {
        String pkg;
        String cls;
        CharSequence label;
        ResolveInfo info;
    }

    private static class OrderComparator implements Comparator<Entry> {
        private final List<String> order;

        OrderComparator(List<String> order) {
            this.order = order;
        }

        @Override
        public int compare(Entry a, Entry b) {
            int ia = order.indexOf(a.pkg);
            int ib = order.indexOf(b.pkg);
            if (ia < 0) ia = Integer.MAX_VALUE;
            if (ib < 0) ib = Integer.MAX_VALUE;
            if (ia != ib) return ia < ib ? -1 : 1;
            return a.label.toString().compareToIgnoreCase(b.label.toString());
        }
    }

    private final List<Entry> entries = new ArrayList<>();
    // Iconos ya escalados al tamano del tile; se invalidan por paquete, no en bloque.
    private final Map<String, Drawable> artCache =
            Collections.synchronizedMap(new HashMap<String, Drawable>());
    private final Handler ui = new Handler(Looper.getMainLooper());
    private final Runnable refresh = new RefreshRunnable();
    private final Runnable clockTick = new ClockRunnable();
    private final BroadcastReceiver packagesChanged = new PackagesReceiver();

    private GridView grid;
    private Adapter adapter;
    private TextView clock;
    private java.text.DateFormat timeFormat;
    private SharedPreferences prefs;
    private float dp;
    private int cellHeight;
    private int tileW;
    private float radius;
    private boolean started;

    private class PackagesReceiver extends BroadcastReceiver {
        @Override
        public void onReceive(Context c, Intent i) {
            Uri data = i.getData();
            if (data != null) artCache.remove(data.getSchemeSpecificPart());
            reload();
        }
    }

    private class RefreshRunnable implements Runnable {
        @Override
        public void run() {
            adapter.notifyDataSetChanged();
        }
    }

    /** Actualiza la hora una vez por minuto, solo mientras el launcher esta visible. */
    private class ClockRunnable implements Runnable {
        @Override
        public void run() {
            long now = System.currentTimeMillis();
            clock.setText(timeFormat.format(new Date(now)));
            ui.postDelayed(this, 60000 - (now % 60000));
        }
    }

    private class ArtLoader extends Thread {
        private final List<Entry> work;

        ArtLoader(List<Entry> work) {
            super("art-loader");
            this.work = work;
        }

        @Override
        public void run() {
            android.os.Process.setThreadPriority(android.os.Process.THREAD_PRIORITY_BACKGROUND);
            PackageManager pm = getPackageManager();
            for (Entry e : work) {
                if (artCache.containsKey(e.pkg)) continue;
                Drawable d = null;
                try {
                    d = e.info.activityInfo.loadBanner(pm);
                    if (d == null) d = e.info.loadIcon(pm);
                } catch (Exception ignored) { }
                // Si la app no trae banner ni icono usable, un unico icono generico.
                if (d == null) d = pm.getDefaultActivityIcon();
                try {
                    artCache.put(e.pkg, scaled(d));
                } catch (Exception ignored) { }
                ui.post(refresh);
            }
        }
    }

    private class MenuClick implements DialogInterface.OnClickListener {
        private final int pos;
        private final int[] actions;

        MenuClick(int pos, int[] actions) {
            this.pos = pos;
            this.actions = actions;
        }

        @Override
        public void onClick(DialogInterface d, int which) {
            runAction(pos, actions[which]);
        }
    }

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        dp = getResources().getDisplayMetrics().density;
        prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        timeFormat = android.text.format.DateFormat.getTimeFormat(this);
        float cellW = (getResources().getDisplayMetrics().widthPixels
                - 2 * 48 * dp - (COLUMNS - 1) * 12 * dp) / COLUMNS;
        cellHeight = (int) (cellW * 9f / 16f);
        tileW = (int) cellW;
        radius = 12 * dp;

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        // Fondo como fondo de ventana: evita una pasada completa de sobredibujo.
        getWindow().setBackgroundDrawable(new ColorDrawable(Color.rgb(16, 20, 26)));
        int side = (int) (48 * dp);
        root.setPadding(side, (int) (12 * dp), side, 0);

        LinearLayout header = new LinearLayout(this);
        header.setGravity(Gravity.END | Gravity.CENTER_VERTICAL);
        clock = new TextView(this);
        clock.setTextColor(Color.rgb(200, 205, 212));
        clock.setTextSize(18);
        header.addView(clock, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        root.addView(header, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, (int) (36 * dp)));

        grid = new GridView(this);
        grid.setNumColumns(COLUMNS);
        grid.setHorizontalSpacing((int) (12 * dp));
        grid.setVerticalSpacing((int) (12 * dp));
        grid.setClipToPadding(false);
        grid.setPadding(0, (int) (8 * dp), 0, (int) (24 * dp));
        grid.setSmoothScrollbarEnabled(false);
        grid.setVerticalScrollBarEnabled(false);
        grid.setDrawSelectorOnTop(true);
        GradientDrawable sel = new GradientDrawable();
        sel.setColor(Color.TRANSPARENT);
        sel.setStroke((int) (3 * dp), Color.WHITE);
        sel.setCornerRadius(radius);
        grid.setSelector(sel);
        grid.setCacheColorHint(Color.TRANSPARENT);
        grid.setScrollingCacheEnabled(false);
        grid.setOverScrollMode(View.OVER_SCROLL_NEVER);

        adapter = new Adapter();
        grid.setAdapter(adapter);
        grid.setOnItemClickListener(this);
        grid.setOnItemLongClickListener(this);

        root.addView(grid, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        setContentView(root);
        reload();
    }

    @Override
    public void onItemClick(AdapterView<?> p, View v, int pos, long id) {
        launch(entries.get(pos));
    }

    @Override
    public boolean onItemLongClick(AdapterView<?> p, View v, int pos, long id) {
        showMenu(pos);
        return true;
    }

    @Override
    protected void onStart() {
        super.onStart();
        IntentFilter f = new IntentFilter();
        f.addAction(Intent.ACTION_PACKAGE_ADDED);
        f.addAction(Intent.ACTION_PACKAGE_REMOVED);
        f.addAction(Intent.ACTION_PACKAGE_CHANGED);
        f.addDataScheme("package");
        registerReceiver(packagesChanged, f);
        ui.post(clockTick);
        if (started) reload();
        started = true;
    }

    @Override
    protected void onStop() {
        super.onStop();
        ui.removeCallbacks(clockTick);
        try { unregisterReceiver(packagesChanged); } catch (Exception ignored) { }
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        if (grid != null && entries.size() > 0) grid.setSelection(0);
    }

    @Override
    public void onBackPressed() {
        // Es el launcher: Atras no hace nada.
    }

    private Set<String> hiddenSet() {
        return new HashSet<>(prefs.getStringSet(KEY_HIDDEN, new HashSet<String>()));
    }

    private List<String> loadOrder() {
        String s = prefs.getString(KEY_ORDER, null);
        if (s == null) return new ArrayList<>(Arrays.asList(DEFAULT_ORDER));
        List<String> out = new ArrayList<>();
        for (String p : s.split(",")) if (p.length() > 0) out.add(p);
        return out;
    }

    private void saveOrderFromEntries() {
        StringBuilder sb = new StringBuilder();
        for (Entry e : entries) {
            if (sb.length() > 0) sb.append(',');
            sb.append(e.pkg);
        }
        prefs.edit().putString(KEY_ORDER, sb.toString()).apply();
    }

    private static boolean isAlwaysHidden(String pkg) {
        for (String h : ALWAYS_HIDDEN) if (h.equals(pkg)) return true;
        return false;
    }

    private void launch(Entry e) {
        Intent i = new Intent(Intent.ACTION_MAIN);
        i.setClassName(e.pkg, e.cls);
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_RESET_TASK_IF_NEEDED);
        try {
            startActivity(i);
            overridePendingTransition(0, 0);
        } catch (Exception ignored) { }
    }

    private void showMenu(int pos) {
        Entry e = entries.get(pos);
        List<String> labels = new ArrayList<>();
        List<Integer> acts = new ArrayList<>();
        if (pos > 0) {
            labels.add("Mover a la izquierda");
            acts.add(ACT_LEFT);
        }
        if (pos < entries.size() - 1) {
            labels.add("Mover a la derecha");
            acts.add(ACT_RIGHT);
        }
        labels.add("Ocultar");
        acts.add(ACT_HIDE);
        labels.add("Información de la app");
        acts.add(ACT_INFO);
        if (!hiddenSet().isEmpty()) {
            labels.add("Restaurar apps ocultas");
            acts.add(ACT_RESTORE);
        }
        int[] actions = new int[acts.size()];
        for (int i = 0; i < actions.length; i++) actions[i] = acts.get(i);
        new AlertDialog.Builder(this)
                .setTitle(e.label)
                .setItems(labels.toArray(new String[0]), new MenuClick(pos, actions))
                .show();
    }

    private void runAction(int pos, int action) {
        Entry e = entries.get(pos);
        switch (action) {
            case ACT_LEFT:
            case ACT_RIGHT: {
                int target = action == ACT_LEFT ? pos - 1 : pos + 1;
                if (target < 0 || target >= entries.size()) return;
                Collections.swap(entries, pos, target);
                saveOrderFromEntries();
                adapter.notifyDataSetChanged();
                grid.setSelection(target);
                break;
            }
            case ACT_HIDE: {
                Set<String> hidden = hiddenSet();
                hidden.add(e.pkg);
                prefs.edit().putStringSet(KEY_HIDDEN, hidden).apply();
                reload();
                grid.setSelection(Math.min(pos, Math.max(entries.size() - 1, 0)));
                break;
            }
            case ACT_INFO: {
                Intent i = new Intent(android.provider.Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                        Uri.parse("package:" + e.pkg));
                i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                try { startActivity(i); } catch (Exception ignored) { }
                break;
            }
            case ACT_RESTORE:
                prefs.edit().remove(KEY_HIDDEN).apply();
                reload();
                break;
            default:
                break;
        }
    }

    private void reload() {
        PackageManager pm = getPackageManager();
        Set<String> hidden = hiddenSet();
        Map<String, Entry> byPkg = new HashMap<>();
        String[] cats = { Intent.CATEGORY_LEANBACK_LAUNCHER, Intent.CATEGORY_LAUNCHER };
        for (String cat : cats) {
            Intent q = new Intent(Intent.ACTION_MAIN).addCategory(cat);
            for (ResolveInfo ri : pm.queryIntentActivities(q, 0)) {
                String pkg = ri.activityInfo.packageName;
                if (pkg.equals(getPackageName()) || byPkg.containsKey(pkg)
                        || isAlwaysHidden(pkg) || hidden.contains(pkg)) continue;
                Entry e = new Entry();
                e.pkg = pkg;
                e.cls = ri.activityInfo.name;
                e.info = ri;
                e.label = ri.loadLabel(pm);
                byPkg.put(pkg, e);
            }
        }
        List<Entry> fresh = new ArrayList<>(byPkg.values());
        Collections.sort(fresh, new OrderComparator(loadOrder()));
        if (!samePackages(fresh)) {
            entries.clear();
            entries.addAll(fresh);
            adapter.notifyDataSetChanged();
        }
        List<Entry> missing = new ArrayList<>();
        for (Entry e : entries) if (!artCache.containsKey(e.pkg)) missing.add(e);
        if (!missing.isEmpty()) new ArtLoader(missing).start();
    }

    /** Misma lista de paquetes en el mismo orden que la que ya se muestra. */
    private boolean samePackages(List<Entry> other) {
        if (other.size() != entries.size()) return false;
        for (int i = 0; i < other.size(); i++) {
            if (!other.get(i).pkg.equals(entries.get(i).pkg)) return false;
        }
        return true;
    }

    /**
     * Prepara el tile completo una sola vez: banner a pantalla completa (o icono centrado sobre
     * el fondo) con las esquinas ya redondeadas. En pantalla solo se pinta un bitmap.
     */
    private Drawable scaled(Drawable d) {
        int tw = tileW;
        int th = cellHeight;
        Bitmap tmp = Bitmap.createBitmap(tw, th, Bitmap.Config.ARGB_8888);
        Canvas ct = new Canvas(tmp);
        ct.drawColor(Color.rgb(28, 36, 48));
        int iw = d.getIntrinsicWidth();
        int ih = d.getIntrinsicHeight();
        if (iw > 0 && ih > 0 && (float) iw / ih >= 1.4f) {
            d.setBounds(0, 0, tw, th); // banner 16:9: ocupa todo el tile
        } else {
            int box = (int) (th * 0.72f); // icono cuadrado: centrado y mas pequeno
            int left = (tw - box) / 2;
            int top = (th - box) / 2;
            d.setBounds(left, top, left + box, top + box);
        }
        d.draw(ct);
        Bitmap out = Bitmap.createBitmap(tw, th, Bitmap.Config.ARGB_8888);
        Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
        paint.setShader(new BitmapShader(tmp, Shader.TileMode.CLAMP, Shader.TileMode.CLAMP));
        new Canvas(out).drawRoundRect(new RectF(0, 0, tw, th), radius, radius, paint);
        tmp.recycle();
        return new BitmapDrawable(getResources(), out);
    }

    private class Adapter extends BaseAdapter {
        @Override public int getCount() { return entries.size(); }
        @Override public Object getItem(int p) { return entries.get(p); }
        @Override public long getItemId(int p) { return p; }

        @Override
        public View getView(int pos, View v, ViewGroup parent) {
            Holder h;
            if (v == null) {
                LinearLayout cell = new LinearLayout(MainActivity.this);
                cell.setOrientation(LinearLayout.VERTICAL);
                ImageView art = new ImageView(MainActivity.this);
                art.setScaleType(ImageView.ScaleType.FIT_XY);
                cell.addView(art, new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT, cellHeight));
                TextView label = new TextView(MainActivity.this);
                label.setTextColor(Color.rgb(200, 205, 212));
                label.setTextSize(13);
                label.setSingleLine(true);
                label.setGravity(Gravity.CENTER_HORIZONTAL);
                label.setPadding(0, (int) (4 * dp), 0, (int) (4 * dp));
                cell.addView(label, new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
                h = new Holder();
                h.art = art;
                h.label = label;
                cell.setTag(h);
                v = cell;
            } else {
                h = (Holder) v.getTag();
            }
            Entry e = entries.get(pos);
            h.art.setImageDrawable(artCache.get(e.pkg));
            h.label.setText(e.label);
            return v;
        }
    }

    private static class Holder {
        ImageView art;
        TextView label;
    }
}
