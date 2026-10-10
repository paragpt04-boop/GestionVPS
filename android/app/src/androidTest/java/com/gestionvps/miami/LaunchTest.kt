package com.gestionvps.miami

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithText
import kotlinx.coroutines.runBlocking
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test

class LaunchTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()

    @Test fun loginScreenLaunches() {
        compose.onNodeWithText("Entrar al panel").assertIsDisplayed()
        compose.onNodeWithText("Usuario administrador").assertIsDisplayed()
    }

    @Test fun miamiTlsTrustAndHostnameAreValid() = runBlocking {
        Api.token = null
        val health = JSONObject(Api.request("/health"))
        assertEquals("ok", health.getString("status"))
    }
}
