package com.mlbb.draftassist

import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.widget.Button
import android.widget.EditText
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity

class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        val apiBaseUrl = findViewById<EditText>(R.id.apiBaseUrl)
        findViewById<Button>(R.id.btnStart).setOnClickListener {
            val base = apiBaseUrl.text?.toString()?.trim().orEmpty()
            if (base.isEmpty()) {
                Toast.makeText(this, "Enter API base URL", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }
            Prefs.setApiBase(this, base.trimEnd('/'))
            ensureOverlayPermissionAndStart()
        }
        findViewById<Button>(R.id.btnStop).setOnClickListener {
            stopService(Intent(this, OverlayService::class.java))
        }
        findViewById<Button>(R.id.btnCredits).setOnClickListener {
            startActivity(Intent(this, CreditsActivity::class.java))
        }
    }

    private fun ensureOverlayPermissionAndStart() {
        if (!Settings.canDrawOverlays(this)) {
            val intent = Intent(
                Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                Uri.parse("package:$packageName")
            )
            startActivity(intent)
            Toast.makeText(this, "Grant overlay permission, then tap Start again", Toast.LENGTH_LONG).show()
            return
        }
        val intent = Intent(this, OverlayService::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(intent)
        } else {
            startService(intent)
        }
    }
}
