package com.frappe.sqlite_mobile

import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.view.View
import android.view.ViewGroup
import android.webkit.WebView
import androidx.activity.enableEdgeToEdge
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.io.File
import java.io.FileOutputStream
import java.net.Socket

class MainActivity : TauriActivity() {
  private var webViewRef: WebView? = null

  override fun onWebViewCreate(webView: WebView) {
    super.onWebViewCreate(webView)
    webViewRef = webView
  }

  override fun onCreate(savedInstanceState: Bundle?) {
    enableEdgeToEdge()

    // Start Chaquopy Python
    if (!Python.isStarted()) {
      Python.start(AndroidPlatform(this))
    }

    // Inject Android paths and env vars before Python runs
    val dataDir = filesDir.absolutePath
    val py = Python.getInstance()
    val os = py.getModule("os")
    val environ = os.get("environ")!!
    environ.callAttr("setdefault", "FRAPPE_SQLITE_DATA_DIR", dataDir)
    environ.callAttr("setdefault", "FRAPPE_SQLITE_BUNDLE_ROOT", "$dataDir/frappe_bundle")
    environ.callAttr("setdefault", "NO_REDIS", "1")
    environ.callAttr("setdefault", "NO_MARIADB", "1")
    environ.callAttr("setdefault", "FRAPPE_SQLITE_DESKTOP", "1")

    // Smoke test: try importing frappe (before starting server)
    try {
      val frappe = py.getModule("frappe")
      Log.d("FrappeSQLite", "Frappe loaded: $frappe")
    } catch (e: Exception) {
      Log.e("FrappeSQLite", "Frappe import failed: ${e.message}", e)
    }

    // Asset extraction on first run
    val bundleDir = File(filesDir, "frappe_bundle")
    val seedSiteDir = File(bundleDir, "resources/seed_site")
    if (!seedSiteDir.exists()) {
      Log.d("FrappeSQLite", "Seed site not found, extracting assets...")
      try {
        copyAssetTree("resources/seed_site", seedSiteDir)
        Log.d("FrappeSQLite", "Asset extraction complete.")
      } catch (e: Exception) {
        Log.e("FrappeSQLite", "Asset extraction failed: ${e.message}", e)
      }
    } else {
      Log.d("FrappeSQLite", "Seed site already exists, skipping extraction.")
    }

    // Start Python server in a background thread
    Thread {
      try {
        Log.d("FrappeSQLite", "Starting Python server thread...")
        val mainModule = py.getModule("runner.main")
        mainModule.callAttr("main")
      } catch (e: Exception) {
        Log.e("FrappeSQLite", "Python server crashed: ${e.message}", e)
      }
    }.start()

    super.onCreate(savedInstanceState)

    // Poll until the Python server is ready, then navigate WebView
    Thread {
      val host = "127.0.0.1"
      val port = 8765
      val maxWaitMs = 60000L
      val pollIntervalMs = 500L
      val startTime = System.currentTimeMillis()
      var ready = false

      while (!ready && (System.currentTimeMillis() - startTime) < maxWaitMs) {
        try {
          Socket(host, port).use {
            ready = true
          }
        } catch (e: Exception) {
          Thread.sleep(pollIntervalMs)
        }
      }

      if (ready) {
        Log.d("FrappeSQLite", "Server is ready, navigating WebView...")
        runOnUiThread {
          try {
            val webView = webViewRef ?: findWebView(findViewById(android.R.id.content))
            webView?.loadUrl("http://$host:$port")
            if (webView != null) {
              Log.d("FrappeSQLite", "Navigated WebView to http://$host:$port")
            } else {
              Log.w("FrappeSQLite", "WebView not found for navigation")
            }
          } catch (e: Exception) {
            Log.e("FrappeSQLite", "WebView navigation failed: ${e.message}", e)
          }
        }
      } else {
        Log.e("FrappeSQLite", "Server did not become ready within ${maxWaitMs}ms")
        runOnUiThread {
          val webView = webViewRef ?: findWebView(findViewById(android.R.id.content))
          webView?.loadUrl("http://$host:$port")
        }
      }
    }.start()
  }

  private fun copyAssetTree(assetPath: String, destPath: File) {
    val children = assets.list(assetPath)
    if (children == null || children.isEmpty()) {
      // assetPath is a file
      destPath.parentFile?.mkdirs()
      assets.open(assetPath).use { input ->
        FileOutputStream(destPath).use { output ->
          input.copyTo(output)
        }
      }
    } else {
      // assetPath is a directory
      destPath.mkdirs()
      for (child in children) {
        copyAssetTree("$assetPath/$child", File(destPath, child))
      }
    }
  }

  private fun findWebView(view: View): WebView? {
    if (view is WebView) return view
    if (view is ViewGroup) {
      for (i in 0 until view.childCount) {
        val found = findWebView(view.getChildAt(i))
        if (found != null) return found
      }
    }
    return null
  }
}
