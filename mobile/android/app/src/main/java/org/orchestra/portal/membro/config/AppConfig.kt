package org.orchestra.portal.membro.config

import org.orchestra.portal.membro.BuildConfig

object AppConfig {
    val apiBaseUrl: String = BuildConfig.API_BASE_URL
    val isDev: Boolean = BuildConfig.FLAVOR == "dev"
}
