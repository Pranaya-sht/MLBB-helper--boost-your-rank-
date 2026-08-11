package com.mlbb.draftassist

import android.content.Context
import org.json.JSONArray
import java.nio.charset.Charset

data class HeroInfo(val name: String, val role: String)

object HeroCatalog {
    fun load(context: Context): List<HeroInfo> {
        val json = context.assets.open("heroes.json").use {
            it.readBytes().toString(Charset.forName("UTF-8"))
        }
        val arr = JSONArray(json)
        val out = ArrayList<HeroInfo>(arr.length())
        for (i in 0 until arr.length()) {
            val obj = arr.getJSONObject(i)
            out.add(
                HeroInfo(
                    name = obj.getString("name"),
                    role = obj.optString("role", "")
                )
            )
        }
        return out.sortedBy { it.name }
    }
}
