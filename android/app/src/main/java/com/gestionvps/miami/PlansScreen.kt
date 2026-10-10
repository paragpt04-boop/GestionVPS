package com.gestionvps.miami

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import org.json.JSONArray
import org.json.JSONObject
import java.math.BigDecimal
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.graphics.Color

private fun quotaText(value: JSONObject, key: String="quota_bytes") = if(value.isNull(key)) "Sin límite de GB" else gb(value.optLong(key))
private fun durationText(value: JSONObject):String {
    if(value.isNull("duration")) return "Sin vencimiento"
    val count=value.optInt("duration")
    return "$count "+if(value.optString("unit")=="months") (if(count==1) "mes" else "meses") else (if(count==1) "día" else "días")
}
private fun bytesFrom(text: String): Long? = runCatching { BigDecimal(text.replace(',','.')).multiply(BigDecimal(1_000_000_000)).longValueExact() }.getOrNull()?.takeIf { it in 1_000_000..1_000_000_000_000_000 }
private fun reasonText(value: String) = when(value) { "expired"->"Venció el plan"; "exhausted"->"Se agotaron los GB"; "cancelled"->"Suscripción cancelada";else->"Plan vigente" }

@Composable
internal fun SubscriptionSummary(sub: JSONObject?) {
    if(sub==null) { Text("Sin plan asignado · sin cuota ni vencimiento",fontSize=12.sp); return }
    Column(verticalArrangement=Arrangement.spacedBy(4.dp)) {
        Text(sub.optString("name"),fontWeight=FontWeight.SemiBold)
        Text(if(sub.isNull("quota_bytes")) "Consumo: ${gb(sub.optLong("used_bytes"))} · sin cuota" else "Disponible: ${gb(sub.optLong("remaining_bytes"))} de ${gb(sub.optLong("quota_bytes"))}",fontSize=14.sp,fontWeight=FontWeight.Medium)
        if(!sub.isNull("quota_bytes")) {
            val total=sub.optLong("quota_bytes").coerceAtLeast(1)
            LinearProgressIndicator(progress={ (sub.optLong("remaining_bytes").toDouble()/total).toFloat().coerceIn(0f,1f) },modifier=Modifier.fillMaxWidth().padding(vertical=4.dp))
        }
        Text(if(sub.isNull("expires")) "Sin vencimiento" else "Vence ${date(sub.optLong("expires"))}",fontSize=12.sp)
        if(!sub.isNull("blocked_reason")) Text(reasonText(sub.optString("blocked_reason")),color=MaterialTheme.colorScheme.error,fontSize=12.sp)
    }
}

@Composable
internal fun PlanPicker(plans: JSONArray, selected: String?, allowNone: Boolean=false, onSelect: (String?)->Unit) {
    var expanded by remember { mutableStateOf(false) }
    val options=arrayObjects(plans)
    val current=options.find { it.optString("id")==selected }
    Box {
        OutlinedButton(onClick={expanded=true},modifier=Modifier.fillMaxWidth()) { Text(current?.optString("name") ?: if(allowNone) "Sin plan · acceso sin cuota" else "Seleccionar plan") }
        DropdownMenu(expanded=expanded,onDismissRequest={expanded=false}) {
            if(allowNone) DropdownMenuItem(text={Text("Sin plan")},onClick={onSelect(null);expanded=false})
            options.forEach { plan -> DropdownMenuItem(text={Column { Text(plan.optString("name"));Text("${durationText(plan)} · ${quotaText(plan)}",fontSize=11.sp) }},onClick={onSelect(plan.getString("id"));expanded=false}) }
        }
    }
    if(options.isEmpty()) Text("Crea tus planes en la pestaña Planes.",fontSize=12.sp)
}

@Composable
fun PlansScreen(model: PanelModel) {
    var editing by remember { mutableStateOf<JSONObject?>(null) }
    var creating by remember { mutableStateOf(false) }
    var archive by remember { mutableStateOf<JSONObject?>(null) }
    LazyColumn(Modifier.fillMaxSize(),contentPadding=PaddingValues(20.dp),verticalArrangement=Arrangement.spacedBy(16.dp)) {
        item { Text("Planes",fontSize=28.sp,fontWeight=FontWeight.SemiBold); Text("Prepara lo que vas a ofrecer a tus clientes.",fontSize=13.sp) }
        item { Button(onClick={creating=true},enabled=!model.busy,modifier=Modifier.fillMaxWidth()) { Text("Crear plan") } }
        item { Text("Editar un plan cambia las nuevas contrataciones. Las suscripciones existentes conservan sus condiciones y su calendario.",fontSize=12.sp) }
        items(arrayObjects(model.plans),key={it.getString("id")}) { plan ->
            Card(colors=CardDefaults.cardColors(containerColor=MaterialTheme.colorScheme.surface),border=BorderStroke(1.dp,Color(0xFFE0E2DC)),shape=RoundedCornerShape(12.dp)) { Column(Modifier.fillMaxWidth().padding(18.dp),verticalArrangement=Arrangement.spacedBy(8.dp)) {
                Text(plan.getString("name"),fontWeight=FontWeight.Bold,fontSize=20.sp)
                Text("${durationText(plan)} · ${quotaText(plan)}")
                Row { TextButton(onClick={editing=plan},enabled=!model.busy){Text("Editar")};TextButton(onClick={archive=plan},enabled=!model.busy){Text("Archivar")} }
            } }
        }
    }
    if(creating||editing!=null) PlanEditor(editing,model.busy,onDismiss={creating=false;editing=null}) { body -> model.action {
        val id=editing?.optString("id")
        Api.request(if(id==null) "/plans" else "/plans/$id",if(id==null) "POST" else "PUT",body)
        model.refresh();creating=false;editing=null
    } }
    archive?.let { plan -> AlertDialog(onDismissRequest={archive=null},title={Text("Archivar ${plan.optString("name")}")},text={Text("Dejará de ofrecerse a nuevos clientes. Los contratos e historiales existentes se conservarán.")},confirmButton={TextButton(enabled=!model.busy,onClick={model.action { Api.request("/plans/${plan.getString("id")}","DELETE");model.refresh();archive=null }}){Text("Archivar")}},dismissButton={TextButton(onClick={archive=null}){Text("Volver")}}) }
}

@Composable
internal fun PlanEditor(plan: JSONObject?, busy: Boolean, onDismiss:()->Unit, onSave:(JSONObject)->Unit) {
    var name by remember { mutableStateOf(plan?.optString("name") ?: "") }
    var duration by remember { mutableStateOf(if(plan==null||plan.isNull("duration")) "" else plan.optInt("duration").toString()) }
    var unit by remember { mutableStateOf(plan?.optString("unit") ?: "days") }
    var quota by remember { mutableStateOf(if(plan==null||plan.isNull("quota_bytes")) "" else BigDecimal(plan.optLong("quota_bytes")).divide(BigDecimal(1_000_000_000)).stripTrailingZeros().toPlainString()) }
    val valid=name.isNotBlank() && (duration.isBlank()||(duration.toIntOrNull() ?: 0) in 1..3650) && (quota.isBlank()||bytesFrom(quota)!=null)
    EditorWindow(title=if(plan==null) "Crear plan" else "Editar plan",subtitle="Define duración y datos incluidos",confirmLabel="Guardar plan",onDismiss=onDismiss,enabled=valid&&!busy,onConfirm={onSave(JSONObject().put("name",name.trim()).put("duration",duration.toIntOrNull() ?: JSONObject.NULL).put("unit",unit).put("quota_bytes",bytesFrom(quota) ?: JSONObject.NULL))}) {
        OutlinedTextField(name,{name=it.take(64)},label={Text("Nombre · ejemplo: Plan Prueba")},singleLine=true)
        Text("Duración del plan",fontSize=15.sp,fontWeight=FontWeight.SemiBold)
        Row { TextButton(onClick={duration="1";unit="days"}){Text("Diario")};TextButton(onClick={duration="7";unit="days"}){Text("Semanal")} }
        Row { TextButton(onClick={duration="1";unit="months"}){Text("Mensual")};TextButton(onClick={duration="3";unit="months"}){Text("Trimestral")} }
        OutlinedTextField(duration,{duration=it.filter(Char::isDigit).take(4)},label={Text(if(unit=="months") "Meses · vacío = sin vencimiento" else "Días · vacío = sin vencimiento")},singleLine=true)
        Row { FilterChip(selected=unit=="days",onClick={unit="days"},label={Text("Días")});Spacer(Modifier.width(8.dp));FilterChip(selected=unit=="months",onClick={unit="months"},label={Text("Meses naturales")}) }
        HorizontalDivider()
        Text("Datos incluidos",fontSize=15.sp,fontWeight=FontWeight.SemiBold)
        OutlinedTextField(quota,{quota=it.take(16)},label={Text("GB · vacío = sin límite")},placeholder={Text("Ejemplo: 2 o 2,5")},singleLine=true,modifier=Modifier.fillMaxWidth())
        Text("Descarga y subida cuentan juntas. El acceso termina cuando venza el tiempo o se agoten los datos.",fontSize=12.sp,color=MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
internal fun SubscriptionDialog(client: JSONObject, model: PanelModel, onDismiss:()->Unit) {
    val sub=client.optJSONObject("subscription")
    val cancelled=sub?.optBoolean("cancelled") ?: false
    var mode by remember { mutableStateOf(if(sub==null||cancelled) "assign" else "topup") }
    var planId by remember { mutableStateOf<String?>(null) }
    var amount by remember { mutableStateOf("") }
    var history by remember { mutableStateOf<JSONArray?>(null) }
    val labels=linkedMapOf("assign" to "Contratar", "topup" to "Añadir GB", "change" to "Cambiar plan", "renew" to "Renovar", "cancel" to "Cancelar suscripción")
    val allowed=if(sub==null||cancelled) listOf("assign") else listOf("topup","change","renew","cancel")
    val valid=when(mode){"assign","change"->planId!=null;"topup"->bytesFrom(amount)!=null&&sub!=null&&!sub.isNull("quota_bytes");else->true}
    EditorWindow(title=client.optString("name"),subtitle="Plan y saldo del cliente",confirmLabel=if(mode=="cancel") "Confirmar cancelación" else "Aplicar",onDismiss=onDismiss,enabled=valid&&!model.busy,onConfirm={model.action {
        val body=JSONObject().put("operation",mode)
        if(mode=="assign"||mode=="change") body.put("plan_id",planId)
        if(mode=="topup") body.put("bytes",bytesFrom(amount))
        Api.request("/clients/${client.getString("id")}/subscription","PUT",body);model.refresh();onDismiss()
    }}) {
        SubscriptionSummary(sub)
        if(client.optBoolean("manually_suspended")) Text("También está suspendido manualmente. Después de ajustar el plan debes reactivarlo desde Clientes.",color=MaterialTheme.colorScheme.error,fontSize=12.sp)
        HorizontalDivider()
        Text("¿Qué necesitas hacer?",fontSize=15.sp,fontWeight=FontWeight.SemiBold)
        FlowRow(horizontalArrangement=Arrangement.spacedBy(8.dp)) {
            allowed.forEach { key -> FilterChip(selected=mode==key,onClick={mode=key;history=null},label={Text(labels.getValue(key))}) }
        }
        when(mode) {
            "assign" -> { PlanPicker(model.plans,planId){planId=it};Text("Comienza un calendario nuevo desde este momento.",fontSize=12.sp) }
            "change" -> { PlanPicker(model.plans,planId){planId=it};Text("Sustituye el saldo por los GB del plan elegido y mantiene tu fecha de facturación. Si ya venció, renueva después. Para cambiar la fecha, cancela y contrata de nuevo.",fontSize=13.sp) }
            "topup" -> { OutlinedTextField(amount,{amount=it.take(16)},label={Text("GB adicionales")},placeholder={Text("Ejemplo: 2")},singleLine=true,modifier=Modifier.fillMaxWidth());Text("Se añaden al saldo sin cambiar el vencimiento. Si ya venció, también debes renovar.",fontSize=13.sp) }
            "renew" -> Text("Repone los GB contratados, sin las recargas, hasta la próxima fecha de facturación. Sustituye el saldo anterior. Antes de vencer, usa Añadir GB. Si el plan es solo de datos, puedes renovar cuando quieras.",fontSize=13.sp)
            "cancel" -> Text("Suspende el acceso y cierra la suscripción. Una contratación posterior iniciará un calendario nuevo. Conserva el perfil WireGuard y el historial.",fontSize=12.sp)
        }
        model.error?.let { Text(it,color=MaterialTheme.colorScheme.error,fontSize=12.sp) }
        TextButton(enabled=!model.busy,onClick={model.action { history=JSONArray(Api.request("/clients/${client.getString("id")}/subscription-history")) }}){Text("Ver historial del plan")}
        history?.let { entries ->
            if(entries.length()==0) Text("Sin operaciones de plan.",fontSize=12.sp)
            arrayObjects(entries).forEach { entry ->
                val details=runCatching { JSONObject(entry.optString("details")) }.getOrNull()
                Text("${date(entry.optLong("ts"))} · ${labels[entry.optString("operation")] ?: entry.optString("operation")}" +
                    (if(details?.has("added_bytes")==true) " · +${gb(details.optLong("added_bytes"))}" else "") +
                    (if(details?.has("plan")==true) " · ${details.optString("plan")}" else ""),fontSize=11.sp)
            }
        }
    }
}
