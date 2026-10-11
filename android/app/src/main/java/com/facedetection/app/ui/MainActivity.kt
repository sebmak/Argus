package com.facedetection.app.ui

import android.annotation.SuppressLint
import android.content.Intent
import android.content.res.Configuration
import android.net.Uri
import android.os.Bundle
import android.view.Menu
import android.view.MenuItem
import android.view.View
import android.webkit.CookieManager
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.facedetection.app.R
import com.facedetection.app.data.ServerConfigManager
import com.facedetection.app.databinding.ActivityMainBinding
import com.google.android.material.navigation.NavigationBarView
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import java.util.concurrent.TimeUnit

/**
 * Rules for MainActivity:
 * 1. Variables must be declared at the top of the class.
 * 2. Asynchronous operations such as telemetry/stats polling must prefer Coroutines.
 * 3. Class documentation comments must be maintained for all changes.
 * 4. Provides native Android navigation (BottomNavigationView for phones, NavigationRailView for foldables/tablets)
 *    and synchronizes tab states with the embedded engine shell.
 */
class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private lateinit var configManager: ServerConfigManager
    private var fileChooserCallback: ValueCallback<Array<Uri>>? = null
    private var isProgrammaticNavSelection: Boolean = false
    private val httpClient: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(4, TimeUnit.SECONDS)
        .readTimeout(4, TimeUnit.SECONDS)
        .build()

    private val filePickerLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (fileChooserCallback == null) return@registerForActivityResult
        val results: Array<Uri>? = if (result.resultCode == RESULT_OK) {
            val clipData = result.data?.clipData
            if (clipData != null) {
                Array(clipData.itemCount) { i -> clipData.getItemAt(i).uri }
            } else {
                result.data?.data?.let { arrayOf(it) }
            }
        } else {
            null
        }
        fileChooserCallback?.onReceiveValue(results)
        fileChooserCallback = null
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        configManager = ServerConfigManager(this)

        if (!configManager.hasConfiguredServer()) {
            launchServerSetup()
            return
        }

        setupToolbar()
        setupNativeNavigation()
        setupWebView()
        setupSwipeRefresh()
        setupBackNavigation()
        setupErrorViewListeners()

        loadServerUrl()
    }

    override fun onConfigurationChanged(newConfig: Configuration) {
        super.onConfigurationChanged(newConfig)
        // Foldable device folded / unfolded: preserve web view while re-binding navigation
        val currentUrl = binding.webView.url
        val currentWeb = binding.webView

        // Remove WebView from previous hierarchy before re-inflating
        (currentWeb.parent as? android.view.ViewGroup)?.removeView(currentWeb)

        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        // Re-attach webView into new layout container
        binding.swipeRefreshLayout.addView(
            currentWeb,
            android.view.ViewGroup.LayoutParams(
                android.view.ViewGroup.LayoutParams.MATCH_PARENT,
                android.view.ViewGroup.LayoutParams.MATCH_PARENT
            )
        )

        setupToolbar()
        setupNativeNavigation()
        setupSwipeRefresh()
        setupErrorViewListeners()

        syncCurrentUrlWithNavigation(currentUrl)
        fetchStatsAndUpdateBadge()
    }

    override fun onCreateOptionsMenu(menu: Menu): Boolean {
        menuInflater.inflate(R.menu.menu_main, menu)
        return true
    }

    override fun onOptionsItemSelected(item: MenuItem): Boolean {
        return when (item.itemId) {
            R.id.action_sandbox -> {
                navigateTab("sandbox", "/sandbox")
                true
            }
            R.id.action_settings -> {
                navigateTab("settings", "/settings")
                true
            }
            R.id.action_refresh -> {
                binding.webView.reload()
                true
            }
            R.id.action_change_server -> {
                launchServerSetup()
                true
            }
            else -> super.onOptionsItemSelected(item)
        }
    }

    private fun setupToolbar() {
        setSupportActionBar(binding.topToolbar)
        val host = configManager.getHost() ?: "Local"
        val port = configManager.getPort()
        binding.topToolbar.subtitle = "$host:$port"
    }

    private fun getActiveNavigationBar(): NavigationBarView? {
        return binding.bottomNavigation ?: binding.navigationRail
    }

    private fun setupNativeNavigation() {
        val navView = getActiveNavigationBar() ?: return

        navView.setOnItemSelectedListener { item ->
            if (isProgrammaticNavSelection) {
                return@setOnItemSelectedListener true
            }

            when (item.itemId) {
                R.id.nav_dashboard -> navigateTab("overview", "/dashboard")
                R.id.nav_review -> navigateTab("review", "/review")
                R.id.nav_household -> navigateTab("persons", "/household")
                R.id.nav_rtsp -> navigateTab("rtsp", "/rtsp")
                R.id.nav_events -> navigateTab("events", "/events")
                R.id.nav_sandbox -> navigateTab("sandbox", "/sandbox")
                R.id.nav_settings -> navigateTab("settings", "/settings")
            }
            true
        }
    }

    private fun navigateTab(tabId: String, path: String) {
        val baseUrl = configManager.getBaseUrl() ?: return

        // Evaluate client-side pushState in WebView for instant native-speed transition
        val js = """
            if (window.history && window.history.pushState) {
                window.history.pushState({ tab: '$tabId' }, '', '$path');
                window.dispatchEvent(new PopStateEvent('popstate', { state: { tab: '$tabId' } }));
            } else {
                window.location.href = '$path';
            }
        """.trimIndent()

        binding.webView.evaluateJavascript(js) { result ->
            // If page is blank or not responding, perform fallback loadUrl
            if (result == null || result == "null") {
                binding.webView.loadUrl(baseUrl.trimEnd('/') + path)
            }
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun setupWebView() {
        val webSettings = binding.webView.settings
        webSettings.javaScriptEnabled = true
        webSettings.domStorageEnabled = true
        webSettings.databaseEnabled = true
        webSettings.allowFileAccess = true
        webSettings.loadWithOverviewMode = true
        webSettings.useWideViewPort = false
        webSettings.textZoom = 100
        binding.webView.isVerticalScrollBarEnabled = true
        binding.webView.isHorizontalScrollBarEnabled = false
        binding.webView.overScrollMode = View.OVER_SCROLL_NEVER
        webSettings.mixedContentMode = WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE
        webSettings.cacheMode = WebSettings.LOAD_DEFAULT
        // Tag user agent so the web app recognizes the native Android companion
        webSettings.userAgentString = "${webSettings.userAgentString} FaceEngineAndroid/1.0"

        val cookieManager = CookieManager.getInstance()
        cookieManager.setAcceptCookie(true)
        cookieManager.setAcceptThirdPartyCookies(binding.webView, true)

        binding.webView.webChromeClient = object : WebChromeClient() {
            override fun onProgressChanged(view: WebView?, newProgress: Int) {
                if (newProgress < 100) {
                    binding.progressBar.visibility = View.VISIBLE
                    binding.progressBar.progress = newProgress
                } else {
                    binding.progressBar.visibility = View.GONE
                }
            }

            override fun onShowFileChooser(
                webView: WebView?,
                filePathCallback: ValueCallback<Array<Uri>>?,
                fileChooserParams: FileChooserParams?
            ): Boolean {
                fileChooserCallback?.onReceiveValue(null)
                fileChooserCallback = filePathCallback

                val intent = fileChooserParams?.createIntent() ?: Intent(Intent.ACTION_GET_CONTENT).apply {
                    type = "image/*"
                    addCategory(Intent.CATEGORY_OPENABLE)
                }

                filePickerLauncher.launch(intent)
                return true
            }
        }

        binding.webView.webViewClient = object : WebViewClient() {
            override fun onPageStarted(view: WebView?, url: String?, favicon: android.graphics.Bitmap?) {
                binding.progressBar.visibility = View.VISIBLE
                injectNativeStyling(view)
            }

            override fun onPageFinished(view: WebView?, url: String?) {
                binding.progressBar.visibility = View.GONE
                binding.swipeRefreshLayout.isRefreshing = false
                binding.errorView.visibility = View.GONE
                injectNativeStyling(view)
                syncCurrentUrlWithNavigation(url)
                fetchStatsAndUpdateBadge()
            }

            override fun doUpdateVisitedHistory(view: WebView?, url: String?, isReload: Boolean) {
                super.doUpdateVisitedHistory(view, url, isReload)
                syncCurrentUrlWithNavigation(url)
            }

            override fun onReceivedError(
                view: WebView?,
                request: WebResourceRequest?,
                error: WebResourceError?
            ) {
                if (request?.isForMainFrame == true) {
                    binding.progressBar.visibility = View.GONE
                    binding.swipeRefreshLayout.isRefreshing = false
                    binding.errorView.visibility = View.VISIBLE
                }
            }
        }
    }

    /**
     * Injects CSS to hide the redundant web header and adjust layout margins for native feel.
     */
    private fun injectNativeStyling(view: WebView?) {
        val js = """
            (function() {
                var styleId = 'native-android-styles';
                var style = document.getElementById(styleId);
                if (!style) {
                    style = document.createElement('style');
                    style.id = styleId;
                    document.head.appendChild(style);
                }
                style.textContent = `
                    header.glass-panel { display: none !important; }
                    html, body {
                        width: 100% !important;
                        max-width: 100vw !important;
                        overflow-x: hidden !important;
                        margin: 0 !important;
                        padding: 0 !important;
                    }
                    main.container {
                        max-width: 100% !important;
                        width: 100% !important;
                        padding: 0.75rem 0.5rem 2rem 0.5rem !important;
                        box-sizing: border-box !important;
                    }
                    .glass-panel, .glass-card {
                        max-width: 100% !important;
                        width: 100% !important;
                        box-sizing: border-box !important;
                    }
                    @media (max-width: 768px) {
                        div[style*="display: grid"],
                        div[style*="display:grid"] {
                            grid-template-columns: 1fr !important;
                            max-width: 100% !important;
                        }
                    }
                `;
            })();
        """.trimIndent()
        view?.evaluateJavascript(js, null)
    }

    /**
     * Synchronizes the native BottomNavigation/NavigationRail indicator with the current web URL.
     */
    private fun syncCurrentUrlWithNavigation(url: String?) {
        if (url.isNullOrBlank()) return
        val navView = getActiveNavigationBar() ?: return

        val targetItemId = when {
            url.endsWith("/review") || url.contains("/review-queue") -> R.id.nav_review
            url.endsWith("/household") || url.contains("/persons") || url.contains("/members") -> R.id.nav_household
            url.endsWith("/rtsp") || url.contains("/stream") || url.contains("/mqtt") -> R.id.nav_rtsp
            url.endsWith("/events") || url.contains("/logs") -> R.id.nav_events
            url.endsWith("/sandbox") || url.contains("/test") -> R.id.nav_sandbox
            url.endsWith("/settings") || url.contains("/config") -> R.id.nav_settings
            url.endsWith("/dashboard") || url.endsWith("/overview") || url.endsWith("/") -> R.id.nav_dashboard
            else -> null
        }

        if (targetItemId != null && navView.selectedItemId != targetItemId) {
            // Check if item exists in this navigation menu (e.g. phone bottom bar has 5 items)
            val menuItem = navView.menu.findItem(targetItemId)
            if (menuItem != null) {
                isProgrammaticNavSelection = true
                navView.selectedItemId = targetItemId
                isProgrammaticNavSelection = false
            }
        }
    }

    /**
     * Coroutine to fetch unread review queue badge telemetry and update native nav badge.
     */
    private fun fetchStatsAndUpdateBadge() {
        val baseUrl = configManager.getBaseUrl() ?: return

        lifecycleScope.launch {
            val unrecognizedCount = withContext(Dispatchers.IO) {
                try {
                    val request = Request.Builder()
                        .url(baseUrl.trimEnd('/') + "/api/v1/stats")
                        .get()
                        .build()
                    val response = httpClient.newCall(request).execute()
                    if (response.isSuccessful) {
                        val body = response.body?.string()
                        if (body != null) {
                            val json = JSONObject(body)
                            json.optInt("unrecognized_count", 0)
                        } else 0
                    } else 0
                } catch (e: Exception) {
                    0
                }
            }

            val navView = getActiveNavigationBar() ?: return@launch
            val badge = navView.getOrCreateBadge(R.id.nav_review)
            if (unrecognizedCount > 0) {
                badge.isVisible = true
                badge.number = unrecognizedCount
            } else {
                badge.isVisible = false
            }
        }
    }

    private fun setupSwipeRefresh() {
        binding.swipeRefreshLayout.setColorSchemeResources(
            R.color.brand_primary,
            R.color.brand_purple,
            R.color.brand_cyan
        )
        binding.swipeRefreshLayout.setProgressBackgroundColorSchemeResource(R.color.bg_surface)
        binding.swipeRefreshLayout.setOnRefreshListener {
            binding.webView.reload()
            fetchStatsAndUpdateBadge()
        }
    }

    private fun setupBackNavigation() {
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (binding.webView.canGoBack()) {
                    binding.webView.goBack()
                } else {
                    isEnabled = false
                    onBackPressedDispatcher.onBackPressed()
                }
            }
        })
    }

    private fun setupErrorViewListeners() {
        binding.btnRetry.setOnClickListener {
            binding.errorView.visibility = View.GONE
            loadServerUrl()
        }

        binding.btnErrorChangeServer.setOnClickListener {
            launchServerSetup()
        }
    }

    private fun loadServerUrl() {
        val baseUrl = configManager.getBaseUrl()
        if (baseUrl != null) {
            binding.errorView.visibility = View.GONE
            binding.webView.loadUrl(baseUrl)
        } else {
            launchServerSetup()
        }
    }

    private fun launchServerSetup() {
        val intent = Intent(this, ServerSetupActivity::class.java)
        startActivity(intent)
    }
}
