package com.gestionvps.miami

import android.graphics.Bitmap
import androidx.compose.ui.graphics.asAndroidBitmap
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import java.io.File

class ClientStatusTest {
    @get:Rule val compose=createComposeRule()
    private fun client(id:String,active:Boolean)=JSONObject().put("id",id).put("name",id)
        .put("ip",if(active) "10.5.0.2" else "10.5.0.3").put("active_estimated",active)
        .put("download_mbps",2).put("upload_mbps",1).put("profile_available",true)
    @Test fun visibleStatusAndReadableGb() {
        val sub=JSONObject().put("name","Plan Semanal").put("quota_bytes",2_000_000_000L)
            .put("remaining_bytes",2_000_000_000L).put("expires",1_800_000_000L)
        val data=JSONObject().put("clients",JSONArray().put(client("Jesús",true).put("subscription",sub)).put(client("María",false)))
        compose.setContent { MiamiTheme { Clients(data,false,{},{_,_->},{}) } }
        compose.onNodeWithText("Activo ahora").assertIsDisplayed()
        compose.onNodeWithText("No activo ahora").assertIsDisplayed()
        compose.onNodeWithText("Disponible: 2 GB de 2 GB").assertIsDisplayed()
        val folder=File(InstrumentationRegistry.getInstrumentation().targetContext.getExternalFilesDir(null),"previews").apply { mkdirs() }
        File(folder,"clientes.png").outputStream().use { compose.onRoot().captureToImage().asAndroidBitmap().compress(Bitmap.CompressFormat.PNG,100,it) }
        compose.onNodeWithText("Activo ahora").performClick()
        compose.onNodeWithText("Actividad de Jesús").assertIsDisplayed()
    }
    @Test fun missingUpdatesDoNotClaimAnActiveConnection() {
        compose.setContent { MiamiTheme { ClientStatus(client("Jesús",true),stale=true) } }
        compose.onNodeWithText("Sin actualizar").assertIsDisplayed()
        compose.onNodeWithText("Activo ahora").assertDoesNotExist()
    }
    @Test fun trafficEvidenceExpiresAndSuspensionOverridesActivity() {
        val tracker=ActivityTracker()
        fun sample(total:Long,suspended:Boolean=false)=JSONObject().put("clients",JSONArray().put(client("a",false).put("sent_bytes",total).put("suspended",suspended)))
        fun active(data:JSONObject)=data.getJSONArray("clients").getJSONObject(0).getBoolean("activity_recent")
        assertFalse(active(tracker.annotate(sample(100),1000)))
        assertTrue(active(tracker.annotate(sample(200),2000)))
        assertFalse(active(tracker.annotate(sample(200),48_000)))
        assertFalse(active(tracker.annotate(sample(300,true),49_000)))
        tracker.clear()
        assertFalse(active(tracker.annotate(sample(300),50_000)))
        assertEquals("2 GB",gb(2_000_000_000L))
        assertEquals("2,5 GB",gb(2_500_000_000L))
        assertEquals("2000 GB",gb(2_000_000_000_000L))
    }
}
