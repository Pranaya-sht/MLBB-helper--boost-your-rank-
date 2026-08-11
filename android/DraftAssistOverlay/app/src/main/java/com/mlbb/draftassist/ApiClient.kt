package com.mlbb.draftassist

import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.TimeUnit

object ApiClient {
    private val client = OkHttpClient.Builder()
        .connectTimeout(8, TimeUnit.SECONDS)
        .readTimeout(20, TimeUnit.SECONDS)
        .build()

    private val jsonMedia = "application/json; charset=utf-8".toMediaType()

    fun draftAdvice(
        apiBase: String,
        allies: List<String>,
        enemies: List<String>,
        banned: List<String>
    ): String {
        val bodyJson = JSONObject()
            .put("allies", JSONArray(allies))
            .put("enemies", JSONArray(enemies))
            .put("banned", JSONArray(banned))
            .put("enemy_items", JSONArray())
            .put("first_pick_side", "blue")

        val request = Request.Builder()
            .url("$apiBase/draft-advice")
            .post(bodyJson.toString().toRequestBody(jsonMedia))
            .build()

        client.newCall(request).execute().use { response ->
            val raw = response.body?.string().orEmpty()
            if (!response.isSuccessful) {
                return "API error ${response.code}: $raw"
            }
            return formatAdvice(JSONObject(raw))
        }
    }

    private fun formatAdvice(obj: JSONObject): String {
        val sb = StringBuilder()
        val win = obj.optDouble("win_probability", Double.NaN)
        if (!win.isNaN()) {
            sb.append("Win prob: ").append(String.format("%.1f%%", win * 100.0)).append('\n')
        }
        sb.append("Source: ").append(obj.optString("scoring_source", "?")).append('\n')
        sb.append(obj.optString("disclaimer", "")).append("\n\n")

        sb.append("Synergy:\n")
        appendChips(sb, obj.optJSONArray("synergy_chips"))
        sb.append("\nCounters:\n")
        appendChips(sb, obj.optJSONArray("counter_chips"))

        val item = obj.optJSONObject("suggested_item")
        if (item != null) {
            sb.append("\nSuggested item: ")
                .append(item.optString("recommended_item"))
                .append(" (")
                .append(item.optString("priority"))
                .append(")\n")
                .append(item.optString("reason"))
                .append('\n')
        }

        val contribs = obj.optJSONArray("hero_contributions")
        if (contribs != null && contribs.length() > 0) {
            sb.append("\nHero contributions:\n")
            for (i in 0 until minOf(contribs.length(), 10)) {
                val c = contribs.getJSONObject(i)
                val low = if (c.optBoolean("low_confidence")) " [limited data]" else ""
                sb.append("- ")
                    .append(c.optString("side"))
                    .append(' ')
                    .append(c.optString("hero"))
                    .append(": ")
                    .append(String.format("%+.3f", c.optDouble("contribution")))
                    .append(low)
                    .append('\n')
            }
        }
        return sb.toString().trim()
    }

    private fun appendChips(sb: StringBuilder, arr: JSONArray?) {
        if (arr == null || arr.length() == 0) {
            sb.append("- (none)\n")
            return
        }
        for (i in 0 until minOf(arr.length(), 8)) {
            val chip = arr.getJSONObject(i)
            val limited = if (chip.optBoolean("low_confidence")) " [limited data]" else ""
            sb.append("- ").append(chip.optString("text")).append(limited).append('\n')
        }
    }
}
