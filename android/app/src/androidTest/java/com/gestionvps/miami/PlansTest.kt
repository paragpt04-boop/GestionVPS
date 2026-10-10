package com.gestionvps.miami

import androidx.compose.material3.MaterialTheme
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import org.json.JSONObject
import org.junit.Rule
import org.junit.Test
import android.graphics.Bitmap
import androidx.compose.ui.graphics.asAndroidBitmap
import androidx.test.platform.app.InstrumentationRegistry
import java.io.File

class PlansTest {
    @get:Rule val compose=createComposeRule()

    @Test fun customPlanEditorSupportsMonthlyPresetAndGb() {
        compose.setContent { MiamiTheme { PlansScreen(PanelModel()) } }
        compose.onNodeWithText("Crear plan").performClick()
        compose.onNodeWithText("Guardar plan").assertIsNotEnabled()
        compose.onNodeWithText("Nombre · ejemplo: Plan Prueba").performTextInput("Plan Mensual VIP")
        compose.onNodeWithText("Mensual").performScrollTo().performClick()
        compose.onNodeWithText("Meses · vacío = sin vencimiento").performScrollTo().assertIsDisplayed()
        compose.onNodeWithText("GB · vacío = sin límite").performScrollTo().performTextInput("25.5")
        compose.onNodeWithText("Guardar plan").assertIsEnabled()
        val folder=File(InstrumentationRegistry.getInstrumentation().targetContext.getExternalFilesDir(null),"previews").apply { mkdirs() }
        File(folder,"crear-plan.png").outputStream().use { compose.onNode(isDialog()).captureToImage().asAndroidBitmap().compress(Bitmap.CompressFormat.PNG,100,it) }
    }

    @Test fun exhaustedSubscriptionAllowsTopupAndCancellation() {
        val client=JSONObject().put("id","test-only").put("name","Cliente de prueba").put("subscription",
            JSONObject().put("name","Plan Semanal").put("quota_bytes",1_000_000_000L).put("remaining_bytes",0L)
                .put("used_bytes",1_000_000_000L).put("expires",1_800_000_000L).put("blocked_reason","exhausted").put("cancelled",false))
        compose.setContent { MiamiTheme { SubscriptionDialog(client,PanelModel(),{}) } }
        compose.onNodeWithText("Se agotaron los GB").assertIsDisplayed()
        compose.onNodeWithText("Aplicar").assertIsNotEnabled()
        compose.onNodeWithText("GB adicionales").performScrollTo().performTextInput("2")
        compose.onNodeWithText("Aplicar").assertIsEnabled()
        compose.onNodeWithText("Cancelar suscripción").performScrollTo().performClick()
        compose.onNodeWithText("Confirmar cancelación").assertIsEnabled()
    }
}
