package com.mlbb.draftassist

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.graphics.PixelFormat
import android.os.Build
import android.os.IBinder
import android.text.Editable
import android.text.TextWatcher
import android.view.Gravity
import android.view.LayoutInflater
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.EditText
import android.widget.Spinner
import android.widget.TextView
import android.widget.Toast
import androidx.core.app.NotificationCompat
import kotlin.concurrent.thread

class OverlayService : Service() {
    companion object {
        const val CHANNEL_ID = "draft_assist_overlay"
        const val NOTIF_ID = 42
        const val ACTION_STOP = "com.mlbb.draftassist.STOP"
    }

    private var windowManager: WindowManager? = null
    private var overlayView: View? = null
    private var layoutParams: WindowManager.LayoutParams? = null

    private val allies = mutableListOf<String>()
    private val enemies = mutableListOf<String>()
    private val banned = mutableListOf<String>()
    private var heroes: List<HeroInfo> = emptyList()
    private var filteredNames: List<String> = emptyList()

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        createChannel()
        startForeground(NOTIF_ID, buildNotification())
        heroes = HeroCatalog.load(this)
        filteredNames = heroes.map { it.name }
        showOverlay()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            stopSelfFully()
            return START_NOT_STICKY
        }
        return START_STICKY
    }

    override fun onDestroy() {
        removeOverlay()
        stopForeground(STOP_FOREGROUND_REMOVE)
        super.onDestroy()
    }

    private fun stopSelfFully() {
        removeOverlay()
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    private fun createChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "Draft Assist Overlay",
                NotificationManager.IMPORTANCE_LOW
            )
            val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            nm.createNotificationChannel(channel)
        }
    }

    private fun buildNotification(): Notification {
        val stopIntent = Intent(this, OverlayService::class.java).apply { action = ACTION_STOP }
        val stopPending = PendingIntent.getService(
            this,
            0,
            stopIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val launch = PendingIntent.getActivity(
            this,
            1,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle(getString(R.string.overlay_notification_title))
            .setContentText(getString(R.string.overlay_notification_text))
            .setSmallIcon(android.R.drawable.ic_menu_compass)
            .setContentIntent(launch)
            .addAction(0, "Stop", stopPending)
            .setOngoing(true)
            .build()
    }

    private fun showOverlay() {
        windowManager = getSystemService(WINDOW_SERVICE) as WindowManager
        val inflater = LayoutInflater.from(this)
        val view = inflater.inflate(R.layout.overlay_panel, null)
        overlayView = view

        val type = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
        } else {
            @Suppress("DEPRECATION")
            WindowManager.LayoutParams.TYPE_PHONE
        }
        val params = WindowManager.LayoutParams(
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.WRAP_CONTENT,
            type,
            WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL or
                WindowManager.LayoutParams.FLAG_WATCH_OUTSIDE_TOUCH,
            PixelFormat.TRANSLUCENT
        )
        params.gravity = Gravity.TOP or Gravity.START
        params.x = 40
        params.y = 120
        layoutParams = params

        val search = view.findViewById<EditText>(R.id.searchHero)
        val spinner = view.findViewById<Spinner>(R.id.slotSpinner)
        val draftState = view.findViewById<TextView>(R.id.draftState)
        val adviceOutput = view.findViewById<TextView>(R.id.adviceOutput)

        val slotAdapter = ArrayAdapter(
            this,
            android.R.layout.simple_spinner_dropdown_item,
            listOf("Ally pick", "Enemy pick", "Ban")
        )
        spinner.adapter = slotAdapter

        fun refreshHeroSpinnerFilter(query: String) {
            filteredNames = heroes.map { it.name }
                .filter { it.contains(query, ignoreCase = true) }
            // Reuse search field suggestions via toast-less adapter on Add
        }

        search.addTextChangedListener(object : TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {
                refreshHeroSpinnerFilter(s?.toString().orEmpty())
            }
            override fun afterTextChanged(s: Editable?) {}
        })

        fun renderState() {
            draftState.text = "Ally: ${allies.joinToString().ifEmpty { "—" }}\n" +
                "Enemy: ${enemies.joinToString().ifEmpty { "—" }}\n" +
                "Banned: ${banned.joinToString().ifEmpty { "—" }}"
        }

        view.findViewById<Button>(R.id.btnAddHero).setOnClickListener {
            val q = search.text?.toString()?.trim().orEmpty()
            val match = filteredNames.firstOrNull { it.equals(q, ignoreCase = true) }
                ?: filteredNames.firstOrNull()
            if (match == null) {
                Toast.makeText(this, "No hero match", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }
            when (spinner.selectedItemPosition) {
                0 -> if (allies.size < 5 && match !in allies) allies.add(match)
                1 -> if (enemies.size < 5 && match !in enemies) enemies.add(match)
                else -> if (banned.size < 10 && match !in banned) banned.add(match)
            }
            search.setText("")
            renderState()
        }

        view.findViewById<Button>(R.id.btnGetAdvice).setOnClickListener {
            adviceOutput.text = "Requesting advice..."
            val api = Prefs.getApiBase(this)
            val a = allies.toList()
            val e = enemies.toList()
            val b = banned.toList()
            thread {
                val text = try {
                    ApiClient.draftAdvice(api, a, e, b)
                } catch (ex: Exception) {
                    "Request failed: ${ex.message}"
                }
                view.post { adviceOutput.text = text }
            }
        }

        view.findViewById<Button>(R.id.btnOverlayStop).setOnClickListener {
            stopSelfFully()
        }

        // Drag to move
        view.setOnTouchListener(object : View.OnTouchListener {
            private var lastX = 0
            private var lastY = 0
            private var initX = 0
            private var initY = 0
            override fun onTouch(v: View?, event: MotionEvent): Boolean {
                val lp = layoutParams ?: return false
                when (event.action) {
                    MotionEvent.ACTION_DOWN -> {
                        lastX = event.rawX.toInt()
                        lastY = event.rawY.toInt()
                        initX = lp.x
                        initY = lp.y
                        return true
                    }
                    MotionEvent.ACTION_MOVE -> {
                        lp.x = initX + (event.rawX.toInt() - lastX)
                        lp.y = initY + (event.rawY.toInt() - lastY)
                        windowManager?.updateViewLayout(overlayView, lp)
                        return true
                    }
                }
                return false
            }
        })

        renderState()
        windowManager?.addView(view, params)
    }

    private fun removeOverlay() {
        val view = overlayView ?: return
        try {
            windowManager?.removeView(view)
        } catch (_: Exception) {
        }
        overlayView = null
    }
}
