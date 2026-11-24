/*
 * SPDX-License-Identifier: Apache-2.0
 */
package org.amnezia.awg

import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.amnezia.awg.activity.MainActivity
import org.amnezia.awg.backend.GoBackend
import org.amnezia.awg.config.BadConfigException
import org.amnezia.awg.config.Config
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import org.junit.runner.RunWith
import java.io.ByteArrayInputStream

/**
 * Runs on a real Android runtime (emulator or device) so that problems which only show up on a
 * given API level are caught: native library loading, desugared Java APIs and activity start-up.
 * It does not bring a tunnel up.
 */
@RunWith(AndroidJUnit4::class)
class SmokeTest {
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext

    private fun parse(text: String) = Config.parse(ByteArrayInputStream(text.toByteArray(Charsets.UTF_8)))

    @Test
    fun installedWithTheRebrandedApplicationId() {
        assertTrue(context.packageName, context.packageName.startsWith("io.routedns.awg"))
    }

    @Test
    fun nativeLibraryLoadsAndReportsAVersion() {
        // The constructor loads libwg-go.so; getVersion() calls into the Go runtime.
        val version = GoBackend(context).version
        assertFalse("empty Go backend version", version.isNullOrBlank())
    }

    @Test
    fun configParsesAndSerializesOnDevice() {
        val config = parse(VALID_CONFIG)
        val userspace = config.toAwgUserspaceString()
        assertTrue(userspace, userspace.contains("jc=4"))
        assertTrue(userspace, userspace.contains("persistent_keepalive_interval=25"))
        assertTrue(config.toAwgQuickString().contains("Jc = 4"))
    }

    @Test
    fun invalidKeepaliveIsRejected() {
        try {
            parse(VALID_CONFIG.replace("PersistentKeepalive = 25", "PersistentKeepalive = 0L"))
            fail("PersistentKeepalive = 0L must be rejected")
        } catch (e: BadConfigException) {
            assertEquals(BadConfigException.Reason.INVALID_NUMBER, e.reason)
        }
    }

    @Test
    fun mainActivityStartsWithoutCrashing() {
        ActivityScenario.launch(MainActivity::class.java).use { scenario ->
            scenario.onActivity { activity -> assertFalse(activity.isFinishing) }
        }
    }

    private companion object {
        const val VALID_CONFIG = """
[Interface]
Address = 192.0.2.2/32
DNS = 192.0.2.0
PrivateKey = TFlmmEUC7V7VtiDYLKsbP5rySTKLIZq1yn8lMqK83wo=
Jc = 4
Jmin = 40
Jmax = 70
[Peer]
AllowedIPs = 0.0.0.0/0
Endpoint = 192.0.2.1:51820
PersistentKeepalive = 25
PublicKey = vBN7qyUTb5lJtWYJ8LhbPio1Z4RcyBPGnqFBGn6O6Qg=
"""
    }
}
