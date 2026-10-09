package com.gestionvps.miami

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import javax.net.ssl.HttpsURLConnection
import java.net.URL

object Api {
    // No SSH secrets, WireGuard private keys or TLS private keys are compiled into the APK.
    private const val base = "https://107.178.51.31:8443"
    @Volatile var token: String? = null
    suspend fun request(path: String, method: String = "GET", body: JSONObject? = null): String = withContext(Dispatchers.IO) {
        val connection = URL(base + path).openConnection() as HttpsURLConnection
        try {
            connection.requestMethod = method
            connection.connectTimeout = 15000
            connection.readTimeout = 90000
            connection.instanceFollowRedirects = false
            connection.setRequestProperty("Accept", "application/json")
            token?.let { connection.setRequestProperty("Authorization", "Bearer $it") }
            if (body != null) {
                connection.doOutput = true
                connection.setRequestProperty("Content-Type", "application/json")
                connection.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
            }
            val code = connection.responseCode
            val text = (if (code in 200..299) connection.inputStream else connection.errorStream)?.bufferedReader()?.use { it.readText() } ?: ""
            if (code !in 200..299) {
                if (code == 401) token = null
                val detail = runCatching { JSONObject(text).optString("detail") }.getOrDefault("")
                throw IllegalStateException(if (detail.isNotBlank() && detail.length < 250) detail else "Error del servidor ($code)")
            }
            text
        } finally { connection.disconnect() }
    }
}
