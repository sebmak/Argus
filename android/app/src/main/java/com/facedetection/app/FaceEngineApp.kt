package com.facedetection.app

import android.app.Application

/**
 * Rules for FaceEngineApp:
 * 1. Global application instance for FaceEngine.
 * 2. Variables must be declared at the top of the class.
 * 3. Class documentation comments must be maintained for all changes.
 */
class FaceEngineApp : Application() {

    override fun onCreate() {
        super.onCreate()
        instance = this
    }

    companion object {
        lateinit var instance: FaceEngineApp
            private set
    }
}
