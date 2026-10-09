package com.gestionvps.miami

import android.graphics.Bitmap
import android.os.Bundle
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.google.zxing.BarcodeFormat
import com.google.zxing.MultiFormatWriter
import org.json.JSONArray
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

private val Mint = Color(0xFF50E3C2)
private val Background = Color(0xFF08131F)
private val Surface = Color(0xFF122333)
private val Muted = Color(0xFF9BADBF)

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
        setContent {
            MaterialTheme(colorScheme = darkColorScheme(primary=Mint,onPrimary=Background,background=Background,surface=Surface,onSurface=Color(0xFFEAF2F8),secondary=Mint)) {
                Panel()
            }
        }
    }
}

private fun arrayObjects(array: JSONArray?): List<JSONObject> = if (array == null) emptyList() else (0 until array.length()).map { array.getJSONObject(it) }
private fun gb(bytes: Long) = String.format(Locale.US,"%.2f GB",bytes/1_000_000_000.0)
private fun date(seconds: Long): String = if (seconds == 0L) "Sin handshake" else SimpleDateFormat("dd MMM · HH:mm",Locale.getDefault()).format(Date(seconds*1000))

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun Panel(model: PanelModel = viewModel()) {
    var tab by remember { mutableIntStateOf(0) }
    var editing by remember { mutableStateOf<JSONObject?>(null) }
    var create by remember { mutableStateOf(false) }
    var confirmation by remember { mutableStateOf<Pair<JSONObject,String>?>(null) }
    var profile by remember { mutableStateOf<JSONObject?>(null) }
    var clientHistory by remember { mutableStateOf<Pair<String,JSONArray>?>(null) }
    var exportError by remember { mutableStateOf<String?>(null) }
    val context = LocalContext.current
    LaunchedEffect(model.logged) {
        if (!model.logged) { profile = null; clientHistory = null; confirmation = null; editing = null; create = false }
    }
    val export = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/octet-stream")) { uri ->
        if (uri != null) {
            runCatching {
                val config = profile?.getString("config") ?: error("El perfil ya no está disponible")
                val output = context.contentResolver.openOutputStream(uri) ?: error("No se pudo abrir el archivo")
                output.use { it.write(config.toByteArray(Charsets.UTF_8)) }
            }.onFailure { exportError = "No se pudo guardar el archivo" }
        }
    }
    if (!model.logged) {
        LoginScreen(model)
        return
    }
    Scaffold(
        containerColor=Background,
        topBar={ TopAppBar(title={ Column { Text("MIAMI",fontWeight=FontWeight.ExtraBold,letterSpacing=3.sp); Text("WIREGUARD CONTROL",fontSize=10.sp,color=Muted,letterSpacing=2.sp) } },
            actions={ IconButton(onClick={model.reload()},enabled=!model.busy){Icon(Icons.Outlined.Refresh,"Actualizar")}; IconButton(onClick={model.logout()},enabled=!model.busy){Icon(Icons.Outlined.Logout,"Cerrar sesión")} },colors=TopAppBarDefaults.topAppBarColors(containerColor=Background)) },
        bottomBar={ NavigationBar(containerColor=Surface) {
            listOf("Resumen","Clientes","Actividad","Sistema").forEachIndexed { index,label ->
                NavigationBarItem(selected=tab==index,onClick={tab=index;if(index==2)model.loadAudit();if(index==3)model.loadDiagnostics()},icon={Icon(listOf(Icons.Outlined.Dashboard,Icons.Outlined.People,Icons.Outlined.History,Icons.Outlined.Settings)[index],label)},label={Text(label,fontSize=11.sp)})
            }
        } },
        floatingActionButton={if(tab==1) FloatingActionButton(onClick={create=true},containerColor=Mint){Icon(Icons.Outlined.Add,"Crear cliente",tint=Background)}}
    ) { padding ->
        Box(Modifier.fillMaxSize().padding(padding)) {
            Column(Modifier.fillMaxSize()) {
                if(model.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
                (model.error ?: exportError)?.let { message ->
                    Text(message,color=Color(0xFFFFB5AE),modifier=Modifier.fillMaxWidth().background(Color(0xFF3B252B)).padding(16.dp))
                }
                val dashboard=model.dashboard
                if(dashboard==null) Box(Modifier.fillMaxSize(),contentAlignment=Alignment.Center){Text("Conectando con Miami…",color=Muted)}
                else when(tab) {
                    0 -> Dashboard(dashboard)
                    1 -> Clients(dashboard,model.busy,onEdit={editing=it},onAction={client,action->
                        if(action=="history") model.action { clientHistory=client.getString("name") to JSONArray(Api.request("/clients/${client.getString("id")}/traffic")) }
                        else confirmation=client to action
                    },onProfile={client->model.action {profile=JSONObject(Api.request("/clients/${client.getString("id")}/profile"))}})
                    2 -> AuditScreen(model.records)
                    else -> SystemScreen(dashboard,model.diagnostic)
                }
            }
        }
    }
    if(create || editing!=null) ClientDialog(editing,onDismiss={create=false;editing=null}) { name,down,up ->
        model.save(editing?.getString("id"),name,down,up);create=false;editing=null
    }
    clientHistory?.let { (name,days) ->
        AlertDialog(onDismissRequest={clientHistory=null},title={Text("Historial · $name")},text={
            LazyColumn(Modifier.heightIn(max=400.dp),verticalArrangement=Arrangement.spacedBy(12.dp)) {
                if(days.length()==0) item { Text("Todavía no hay muestras de tráfico.") }
                items(arrayObjects(days)) { day ->
                    Column { Text(day.getString("day"),fontWeight=FontWeight.Bold);Text("↓ ${gb(day.optLong("sent_bytes"))} · ↑ ${gb(day.optLong("received_bytes"))}",color=Mint) }
                }
            }
        },confirmButton={TextButton(onClick={clientHistory=null}){Text("Cerrar")}})
    }
    confirmation?.let { (client,operation) ->
        val verb=mapOf("delete" to "Eliminar","suspend" to "Suspender","activate" to "Reactivar","rotate" to "Renovar claves")[operation] ?: operation
        AlertDialog(onDismissRequest={confirmation=null},title={Text("$verb · ${client.getString("name")}")},text={Text(when(operation){"delete"->"Se revocará el acceso y se eliminará el perfil del servidor. El historial se conservará.";"rotate"->"El perfil anterior dejará de funcionar. Tendrás que entregar el nuevo archivo o QR al cliente.";"suspend"->"El cliente perderá acceso a la VPN hasta que lo reactives.";else->"El cliente podrá volver a conectarse con su perfil."})},confirmButton={TextButton(onClick={model.operate(client.getString("id"),operation);confirmation=null}){Text(verb)}},dismissButton={TextButton(onClick={confirmation=null}){Text("Cancelar")}})
    }
    profile?.let { value ->
        val config=value.getString("config")
        val bitmap=remember(config){ qr(config) }
        AlertDialog(onDismissRequest={profile=null},title={Text(value.getString("name"))},text={Column(horizontalAlignment=Alignment.CenterHorizontally){Text("Perfil WireGuard",color=Mint);Spacer(Modifier.height(12.dp));Image(bitmap.asImageBitmap(),"QR privado de conexión",Modifier.fillMaxWidth().aspectRatio(1f));Spacer(Modifier.height(12.dp));Text("Este QR y el archivo contienen la clave privada del cliente. Entrégalos solo a su propietario.",fontSize=12.sp,color=Muted)}},confirmButton={TextButton(onClick={export.launch(value.getString("name").replace(Regex("[^a-zA-Z0-9_-]"),"_").take(48).ifBlank{"cliente"}+".conf")}){Text("Guardar .conf")}},dismissButton={TextButton(onClick={profile=null}){Text("Cerrar")}})
    }
}

@Composable
fun LoginScreen(model:PanelModel) {
    var username by remember { mutableStateOf("admin") }
    var password by remember { mutableStateOf("") }
    Box(Modifier.fillMaxSize().background(Background).systemBarsPadding().imePadding().padding(24.dp),contentAlignment=Alignment.Center) {
        Column(Modifier.widthIn(max=440.dp).verticalScroll(rememberScrollState()),verticalArrangement=Arrangement.spacedBy(18.dp)) {
            Icon(Icons.Outlined.Shield,"",tint=Mint,modifier=Modifier.size(58.dp))
            Text("Tu red.\nBajo control.",fontSize=38.sp,lineHeight=43.sp,fontWeight=FontWeight.Bold)
            Text("MIAMI / PANEL ADMINISTRATIVO",color=Mint,fontSize=11.sp,letterSpacing=2.sp)
            Text("Gestiona tus clientes WireGuard desde una conexión segura.",color=Muted)
            OutlinedTextField(username,{username=it},label={Text("Usuario administrador")},singleLine=true,modifier=Modifier.fillMaxWidth(),enabled=!model.busy)
            OutlinedTextField(password,{password=it},label={Text("Contraseña")},singleLine=true,visualTransformation=PasswordVisualTransformation(),modifier=Modifier.fillMaxWidth(),enabled=!model.busy)
            model.error?.let{Text(it,color=Color(0xFFFFB5AE))}
            Button(onClick={model.login(username,password);password=""},enabled=!model.busy&&username.isNotBlank()&&password.isNotEmpty(),modifier=Modifier.fillMaxWidth().height(54.dp),shape=RoundedCornerShape(14.dp)){Text(if(model.busy)"Conectando…" else "Entrar al panel",fontWeight=FontWeight.Bold)}
            Text("107.178.51.31 · HTTPS\nLa sesión dura una hora y no se guarda en el dispositivo.",color=Muted,fontSize=12.sp)
        }
    }
}

@Composable
fun Dashboard(data:JSONObject) {
    val clients=arrayObjects(data.optJSONArray("clients"))
    val sent=clients.sumOf{it.optLong("sent_bytes")};val received=clients.sumOf{it.optLong("received_bytes")}
    LazyColumn(Modifier.fillMaxSize(),contentPadding=PaddingValues(20.dp),verticalArrangement=Arrangement.spacedBy(18.dp)) {
        item { Text("Vista general",fontSize=28.sp,fontWeight=FontWeight.Bold);Text("Actualizado ${date(data.optLong("timestamp"))} · cada 15 s",fontSize=12.sp,color=Muted) }
        item { Card(colors=CardDefaults.cardColors(containerColor=Color(0xFF123C3D)),shape=RoundedCornerShape(22.dp)) {
            Column(Modifier.fillMaxWidth().padding(22.dp)) {
                Text("MIAMI · SERVIDOR VPN",color=Mint,fontSize=12.sp,letterSpacing=1.sp)
                Spacer(Modifier.height(12.dp));Text("107.178.51.31",fontSize=28.sp,fontWeight=FontWeight.Bold)
                Spacer(Modifier.height(8.dp));Text("wg0   /   10.5.0.0/24   /   UDP 51820",color=Color(0xFFB5D8D1),fontSize=12.sp)
                Spacer(Modifier.height(20.dp));Text("${clients.count{it.optBoolean("active_estimated")}} conexiones recientes",fontWeight=FontWeight.SemiBold)
                Text("Estimación por handshake en los últimos 3 minutos",fontSize=11.sp,color=Muted)
            }
        } }
        item { Row(horizontalArrangement=Arrangement.spacedBy(12.dp)) { Metric("Clientes",clients.size.toString(),Modifier.weight(1f));Metric("Suspendidos",clients.count{it.optBoolean("suspended")}.toString(),Modifier.weight(1f)) } }
        item { Row(horizontalArrangement=Arrangement.spacedBy(12.dp)) { Metric("Descarga clientes",gb(sent),Modifier.weight(1f));Metric("Subida clientes",gb(received),Modifier.weight(1f)) } }
        items(arrayObjects(data.optJSONArray("alerts"))) { alert -> Card(colors=CardDefaults.cardColors(containerColor=Color(0xFF413725))){Text("Aviso · ${alert.optString("message")}",Modifier.fillMaxWidth().padding(16.dp),color=Color(0xFFFFD48A))} }
        item { Text("Historial diario · UTC",fontSize=20.sp,fontWeight=FontWeight.SemiBold) }
        val history=arrayObjects(data.optJSONArray("history"))
        if(history.isEmpty()) item{Text("El historial aparecerá al recoger las primeras muestras.",color=Muted)}
        items(history){ day -> Card { Column(Modifier.fillMaxWidth().padding(16.dp)){Text(day.getString("day"),fontWeight=FontWeight.SemiBold);Spacer(Modifier.height(6.dp));Text("↓ ${gb(day.optLong("sent_bytes"))}     ↑ ${gb(day.optLong("received_bytes"))}",color=Mint)} } }
        item { Text("Sin cuota mensual. El historial comienza con la instalación; no reconstruye tráfico anterior. Puede faltar tráfico entre la última muestra y un reinicio.",fontSize=12.sp,color=Muted) }
    }
}

@Composable
fun Metric(label:String,value:String,modifier:Modifier) {
    Card(modifier,shape=RoundedCornerShape(18.dp)) { Column(Modifier.padding(16.dp)){Text(label,fontSize=12.sp,color=Muted);Spacer(Modifier.height(8.dp));Text(value,fontSize=24.sp,fontWeight=FontWeight.Bold)} }
}

@Composable
fun Clients(data:JSONObject,busy:Boolean,onEdit:(JSONObject)->Unit,onAction:(JSONObject,String)->Unit,onProfile:(JSONObject)->Unit) {
    var query by remember { mutableStateOf("") }
    val clients=arrayObjects(data.optJSONArray("clients")).filter{it.getString("name").contains(query,true)||it.getString("ip").contains(query)}
    LazyColumn(Modifier.fillMaxSize(),contentPadding=PaddingValues(start=20.dp,end=20.dp,top=20.dp,bottom=100.dp),verticalArrangement=Arrangement.spacedBy(14.dp)) {
        item{Text("Clientes",fontSize=28.sp,fontWeight=FontWeight.Bold);Text("Perfiles individuales. Velocidades independientes.",fontSize=12.sp,color=Muted)}
        item{OutlinedTextField(query,{query=it},label={Text("Buscar nombre o IP")},leadingIcon={Icon(Icons.Outlined.Search,null)},modifier=Modifier.fillMaxWidth(),singleLine=true)}
        if(clients.isEmpty()) item{Text("No hay clientes que mostrar. Usa + para crear uno.",color=Muted,modifier=Modifier.padding(vertical=24.dp))}
        items(clients,key={it.getString("id")}){client->
            Card(shape=RoundedCornerShape(20.dp)) { Column(Modifier.fillMaxWidth().padding(18.dp),verticalArrangement=Arrangement.spacedBy(10.dp)) {
                Row(verticalAlignment=Alignment.CenterVertically){
                    Box(Modifier.size(42.dp).background(Color(0xFF214940),RoundedCornerShape(12.dp)),contentAlignment=Alignment.Center){Text(client.getString("name").take(1).uppercase(),color=Mint,fontWeight=FontWeight.Bold)}
                    Spacer(Modifier.width(12.dp));Column(Modifier.weight(1f)){Text(client.getString("name"),fontWeight=FontWeight.Bold,fontSize=19.sp);Text(client.getString("ip"),color=Muted,fontSize=12.sp)}
                    var menu by remember { mutableStateOf(false) }
                    Box{IconButton(onClick={menu=true},enabled=!busy){Icon(Icons.Outlined.MoreVert,"Acciones")};DropdownMenu(expanded=menu,onDismissRequest={menu=false}){
                        DropdownMenuItem(text={Text("Editar nombre y velocidad")},onClick={menu=false;onEdit(client)})
                        DropdownMenuItem(text={Text("Historial de tráfico")},onClick={menu=false;onAction(client,"history")})
                        DropdownMenuItem(text={Text(if(client.optBoolean("suspended"))"Reactivar" else "Suspender")},onClick={menu=false;onAction(client,if(client.optBoolean("suspended"))"activate" else "suspend")})
                        DropdownMenuItem(text={Text("Renovar claves")},onClick={menu=false;onAction(client,"rotate")})
                        DropdownMenuItem(text={Text("Eliminar",color=Color(0xFFFFB5AE))},onClick={menu=false;onAction(client,"delete")})
                    }}
                }
                Text(if(client.optBoolean("suspended"))"SUSPENDIDO" else if(client.optBoolean("active_estimated"))"HANDSHAKE RECIENTE" else "SIN HANDSHAKE RECIENTE",color=if(client.optBoolean("active_estimated"))Mint else Muted,fontSize=10.sp,letterSpacing=1.sp)
                Text("↓ ${client.getInt("download_mbps")} Mbps     ↑ ${client.getInt("upload_mbps")} Mbps",fontWeight=FontWeight.SemiBold)
                Text("Tráfico: ↓ ${gb(client.optLong("sent_bytes"))} · ↑ ${gb(client.optLong("received_bytes"))}",fontSize=12.sp,color=Muted)
                Text("Último handshake: ${date(client.optLong("last_handshake"))}",fontSize=11.sp,color=Muted)
                OutlinedButton(onClick={onProfile(client)},enabled=!busy&&!client.optBoolean("suspended")&&client.optBoolean("profile_available"),modifier=Modifier.fillMaxWidth()){Icon(Icons.Outlined.QrCode,"",Modifier.size(18.dp));Spacer(Modifier.width(8.dp));Text("Perfil .conf y código QR")}
            } }
        }
    }
}

@Composable
fun ClientDialog(client:JSONObject?,onDismiss:()->Unit,onSave:(String,Int,Int)->Unit) {
    var name by remember {mutableStateOf(client?.getString("name") ?: "")}
    var down by remember {mutableStateOf((client?.getInt("download_mbps") ?: 2).toString())}
    var up by remember {mutableStateOf((client?.getInt("upload_mbps") ?: 1).toString())}
    val valid=name.trim().isNotEmpty()&&name.length<=64&&(down.toIntOrNull() ?: 0) in 1..1000&&(up.toIntOrNull() ?: 0) in 1..1000
    AlertDialog(onDismissRequest=onDismiss,title={Text(if(client==null)"Nuevo cliente" else "Editar cliente")},text={Column(Modifier.verticalScroll(rememberScrollState()),verticalArrangement=Arrangement.spacedBy(12.dp)){
        Text("Elige el nombre que quieras. La IP y las claves se asignan automáticamente.",color=Muted,fontSize=12.sp)
        OutlinedTextField(name,{name=it.take(64)},label={Text("Nombre o usuario")},singleLine=true)
        OutlinedTextField(down,{down=it.filter(Char::isDigit).take(4)},label={Text("Descarga · Mbps")},singleLine=true)
        OutlinedTextField(up,{up=it.filter(Char::isDigit).take(4)},label={Text("Subida · Mbps")},singleLine=true)
        Text("De 1 a 1000 Mbps. Sin cuota mensual de GB.",fontSize=11.sp,color=Muted)
    }},confirmButton={TextButton(onClick={onSave(name.trim(),down.toInt(),up.toInt())},enabled=valid){Text("Guardar")}},dismissButton={TextButton(onClick=onDismiss){Text("Cancelar")}})
}

@Composable
fun AuditScreen(text:String) {
    val entries=runCatching{arrayObjects(JSONArray(text))}.getOrDefault(emptyList())
    val labels=mapOf("create" to "Cliente creado","update" to "Cliente actualizado","suspend" to "Acceso suspendido","activate" to "Acceso reactivado","delete" to "Acceso revocado","rotate" to "Claves renovadas","export_profile" to "Perfil consultado","import_existing" to "Configuración existente importada")
    LazyColumn(contentPadding=PaddingValues(20.dp),verticalArrangement=Arrangement.spacedBy(12.dp)) {
        item{Text("Actividad",fontSize=28.sp,fontWeight=FontWeight.Bold);Text("Últimas 200 operaciones administrativas",color=Muted,fontSize=12.sp)}
        items(entries){row->Card{Column(Modifier.fillMaxWidth().padding(16.dp)){Text(labels[row.optString("action")] ?: row.optString("action"),fontWeight=FontWeight.SemiBold);Text(date(row.optLong("ts")),color=Muted,fontSize=12.sp);if(!row.isNull("client_id"))Text("ID: ${row.optString("client_id").take(8)}",color=Muted,fontSize=11.sp)}}}
    }
}

@Composable
fun SystemScreen(data:JSONObject,diagnostic:String) {
    LazyColumn(contentPadding=PaddingValues(20.dp),verticalArrangement=Arrangement.spacedBy(16.dp)) {
        item{Text("Sistema",fontSize=28.sp,fontWeight=FontWeight.Bold);Text("Diagnóstico de solo lectura",color=Muted)}
        item{Metric("Tiempo encendido","${(data.optDouble("uptime_seconds")/3600).toInt()} h",Modifier.fillMaxWidth())}
        item{Metric("Carga media",String.format(Locale.US,"%.2f",data.optDouble("load")),Modifier.fillMaxWidth())}
        item {
            Card {
                Column(Modifier.padding(16.dp)) {
                    Text("Servicios", fontWeight=FontWeight.Bold)
                    val services=data.optJSONObject("services")
                    services?.keys()?.forEach { key ->
                        Text("$key · ${services.optString(key)}",fontSize=12.sp,color=Muted,modifier=Modifier.padding(top=8.dp))
                    }
                }
            }
        }
        val diag=runCatching{JSONObject(diagnostic)}.getOrNull()
        diag?.keys()?.forEach{key->item{Card{Column(Modifier.padding(16.dp)){Text(key,fontWeight=FontWeight.SemiBold,color=Mint);Text(diag.optString(key),fontSize=10.sp,lineHeight=15.sp,color=Muted)}}}}
        item{Text("Las conexiones se estiman por handshake. Una alerta de servicio requiere revisión; este panel no reinicia SSH ni el VPS.",color=Muted,fontSize=12.sp)}
    }
}

private fun qr(text:String):Bitmap {
    val matrix=MultiFormatWriter().encode(text,BarcodeFormat.QR_CODE,640,640)
    val pixels=IntArray(640*640){index->if(matrix[index%640,index/640])android.graphics.Color.BLACK else android.graphics.Color.WHITE}
    return Bitmap.createBitmap(pixels,640,640,Bitmap.Config.ARGB_8888)
}
