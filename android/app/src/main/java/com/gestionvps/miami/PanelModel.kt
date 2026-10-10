package com.gestionvps.miami

import androidx.compose.runtime.*
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.*
import org.json.JSONObject
import org.json.JSONArray

class PanelModel : ViewModel() {
    var logged by mutableStateOf(false)
    var busy by mutableStateOf(false)
    var error by mutableStateOf<String?>(null)
    var dashboard by mutableStateOf<JSONObject?>(null)
    var records by mutableStateOf("")
    var diagnostic by mutableStateOf("")
    var plans by mutableStateOf(JSONArray())
    private var polling: Job? = null
    private val activity=ActivityTracker()

    fun login(username: String, password: String) = action {
        val result = JSONObject(Api.request("/login", "POST", JSONObject().put("username", username).put("password", password)))
        Api.token = result.getString("token")
        logged = true
        refresh()
        polling?.cancel()
        polling = viewModelScope.launch { while (isActive && logged) { delay(5000); runCatching { refresh() }.onFailure { error = message(it); if (Api.token == null) logged = false } } }
    }
    fun logout() = action {
        try { Api.request("/logout", "POST") } finally { Api.token = null; logged = false; polling?.cancel(); dashboard = null; activity.clear();plans=JSONArray() }
    }
    suspend fun refresh() { dashboard = activity.annotate(JSONObject(Api.request("/dashboard")),android.os.SystemClock.elapsedRealtime()); plans = JSONArray(Api.request("/plans")) }
    fun reload() = action { refresh() }
    fun save(id: String?, name: String, down: Int, up: Int, planId: String?) = action {
        val body=JSONObject().put("name",name).put("download_mbps",down).put("upload_mbps",up)
        if (id==null && planId!=null) body.put("plan_id",planId)
        Api.request(if (id == null) "/clients" else "/clients/$id", if (id == null) "POST" else "PUT", body); refresh()
    }
    fun operate(id: String, operation: String) = action {
        Api.request("/clients/$id" + if (operation == "delete") "" else "/$operation", if (operation == "delete") "DELETE" else "POST"); refresh()
    }
    fun loadAudit() = action { records = Api.request("/audit") }
    fun loadDiagnostics() = action { diagnostic = Api.request("/diagnostics") }
    fun action(block: suspend () -> Unit) {
        if (busy) return
        viewModelScope.launch {
            busy = true; error = null
            try { block() } catch (e: Exception) { error = message(e); if (Api.token == null) logged = false } finally { busy = false }
        }
    }
    private fun message(e: Throwable): String = if (e is IllegalStateException) e.message ?: "Operación fallida" else "No se pudo conectar de forma segura. Comprueba Internet y el estado de la API."
}
