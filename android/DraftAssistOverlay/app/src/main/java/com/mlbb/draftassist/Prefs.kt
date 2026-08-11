package com.mlbb.draftassist

import android.content.Context

object Prefs {
    private const val NAME = "draft_assist_prefs"
    private const val KEY_API = "api_base"

    fun setApiBase(context: Context, value: String) {
        context.getSharedPreferences(NAME, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY_API, value)
            .apply()
    }

    fun getApiBase(context: Context): String {
        return context.getSharedPreferences(NAME, Context.MODE_PRIVATE)
            .getString(KEY_API, "http://192.168.1.10:8000")
            ?: "http://192.168.1.10:8000"
    }
}
