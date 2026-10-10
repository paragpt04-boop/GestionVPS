package com.gestionvps.miami

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Close
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties

/** Spacious form with a persistent action area, including when the keyboard opens. */
@Composable
internal fun EditorWindow(title:String,subtitle:String,confirmLabel:String,onDismiss:()->Unit,
                          enabled:Boolean=true,onConfirm:()->Unit,content:@Composable ColumnScope.()->Unit) {
    val maxHeight=(LocalConfiguration.current.screenHeightDp*0.9f).dp
    Dialog(onDismissRequest=onDismiss,properties=DialogProperties(usePlatformDefaultWidth=false)) {
        Surface(Modifier.imePadding().padding(12.dp).widthIn(max=600.dp).fillMaxWidth().heightIn(max=maxHeight),
            shape=MaterialTheme.shapes.large,color=MaterialTheme.colorScheme.surface,tonalElevation=0.dp) {
            Column {
                Row(Modifier.fillMaxWidth().padding(start=22.dp,top=16.dp,end=8.dp,bottom=12.dp),verticalAlignment=Alignment.Top) {
                    Column(Modifier.weight(1f)) { Text(title,fontSize=23.sp,fontWeight=FontWeight.SemiBold);Spacer(Modifier.height(4.dp));Text(subtitle,fontSize=13.sp,color=MaterialTheme.colorScheme.onSurfaceVariant) }
                    IconButton(onClick=onDismiss){Icon(Icons.Outlined.Close,"Cerrar ventana")}
                }
                HorizontalDivider()
                Column(Modifier.weight(1f,fill=false).verticalScroll(rememberScrollState()).padding(22.dp),verticalArrangement=Arrangement.spacedBy(14.dp),content=content)
                HorizontalDivider()
                Row(Modifier.fillMaxWidth().padding(16.dp),horizontalArrangement=Arrangement.spacedBy(12.dp),verticalAlignment=Alignment.CenterVertically) {
                    TextButton(onClick=onDismiss){Text("Volver")}
                    Button(onClick=onConfirm,enabled=enabled,modifier=Modifier.weight(1f).heightIn(min=48.dp),shape=MaterialTheme.shapes.medium){Text(confirmLabel)}
                }
            }
        }
    }
}
