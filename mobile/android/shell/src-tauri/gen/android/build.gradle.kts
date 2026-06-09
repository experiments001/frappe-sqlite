buildscript {
    repositories {
        google()
        mavenCentral()
        maven { url = uri("https://chaquo.com/maven") }
    }
    dependencies {
        classpath("com.android.tools.build:gradle:8.2.0")
        classpath("org.jetbrains.kotlin:kotlin-gradle-plugin:1.9.25")
        classpath("com.chaquo.python:gradle:15.0.1")

    }
}

allprojects {
    repositories {
        google()
        mavenCentral()
    }
}

tasks.register("clean").configure {
    delete("build")
}

