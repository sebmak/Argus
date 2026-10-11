package com.facedetection.app.ui.components

import android.graphics.Bitmap
import android.graphics.Paint
import android.graphics.RectF
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.unit.dp
import com.facedetection.app.data.models.DetectedFace
import com.facedetection.app.ui.theme.BgSurfaceCard
import com.facedetection.app.ui.theme.BorderSubtle
import com.facedetection.app.ui.theme.BrandAmber
import com.facedetection.app.ui.theme.BrandEmerald

/**
 * Renders an image with overlayed facial bounding boxes and label badges.
 */
@Composable
fun BoundingBoxCanvas(
    bitmap: Bitmap,
    faces: List<DetectedFace>,
    modifier: Modifier = Modifier
) {
    val imageAspectRatio = if (bitmap.height > 0) bitmap.width.toFloat() / bitmap.height.toFloat() else 1f

    Box(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .border(1.dp, BorderSubtle, RoundedCornerShape(12.dp))
            .background(BgSurfaceCard)
    ) {
        Canvas(
            modifier = Modifier
                .fillMaxWidth()
                .aspectRatio(imageAspectRatio)
        ) {
            val scaleX = size.width / bitmap.width.toFloat()
            val scaleY = size.height / bitmap.height.toFloat()

            // Draw underlying bitmap
            drawImage(
                image = bitmap.asImageBitmap(),
                dstSize = androidx.compose.ui.unit.IntSize(size.width.toInt(), size.height.toInt())
            )

            // Draw bounding boxes and tags
            faces.forEach { face ->
                val box = face.bbox
                if (box.size >= 4) {
                    val left = box[0] * scaleX
                    val top = box[1] * scaleY
                    val right = box[2] * scaleX
                    val bottom = box[3] * scaleY

                    val boxWidth = right - left
                    val boxHeight = bottom - top

                    val isRecognized = face.isRecognized
                    val strokeColor = if (isRecognized) BrandEmerald else BrandAmber
                    val labelText = if (isRecognized) {
                        "${face.matchedName} (${String.format("%.1f%%", face.confidence * 100)})"
                    } else {
                        "Unknown (${String.format("%.1f%%", face.confidence * 100)})"
                    }

                    // Draw bounding box
                    drawRect(
                        color = strokeColor,
                        topLeft = Offset(left, top),
                        size = Size(boxWidth, boxHeight),
                        style = Stroke(width = 3.dp.toPx())
                    )

                    // Draw text badge using native canvas paint
                    drawContext.canvas.nativeCanvas.apply {
                        val textPaint = Paint().apply {
                            color = android.graphics.Color.WHITE
                            textSize = 12.dp.toPx()
                            isFakeBoldText = true
                            isAntiAlias = true
                        }

                        val bgPaint = Paint().apply {
                            color = strokeColor.toArgb()
                            style = Paint.Style.FILL
                            isAntiAlias = true
                        }

                        val textWidth = textPaint.measureText(labelText)
                        val textHeight = 14.dp.toPx()
                        val padding = 6.dp.toPx()

                        val badgeTop = (top - textHeight - (padding * 2)).coerceAtLeast(0f)
                        val badgeBottom = badgeTop + textHeight + (padding * 2)
                        val badgeLeft = left.coerceAtLeast(0f)
                        val badgeRight = badgeLeft + textWidth + (padding * 2)

                        drawRoundRect(
                            RectF(badgeLeft, badgeTop, badgeRight, badgeBottom),
                            6.dp.toPx(),
                            6.dp.toPx(),
                            bgPaint
                        )

                        drawText(
                            labelText,
                            badgeLeft + padding,
                            badgeBottom - padding - 2f,
                            textPaint
                        )
                    }
                }
            }
        }
    }
}
