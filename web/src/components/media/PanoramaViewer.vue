<template>
  <div ref="host" class="pano">
    <canvas ref="canvas" class="pano-canvas"></canvas>
    <div v-if="loading" class="pano-mask">全景加载中…</div>
    <div v-else-if="error" class="pano-mask">{{ error }}</div>
    <div class="pano-tip">拖动旋转 · 滚轮缩放 · 双击复位</div>
  </div>
</template>

<script setup lang="ts">
/**
 * 轻量 360° 全景查看器：WebGL 全屏四边形 + 等距柱状投影采样，无第三方依赖。
 * 支持鼠标/触摸拖动改变视角、滚轮缩放视野。
 */
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps<{ src: string }>()

const host = ref<HTMLDivElement | null>(null)
const canvas = ref<HTMLCanvasElement | null>(null)
const loading = ref(true)
const error = ref('')

const VERT_SRC = `
attribute vec2 aPos;
uniform float uFov;
uniform float uAspect;
uniform float uYaw;
uniform float uPitch;
varying vec3 vDir;
void main() {
  float t = tan(uFov * 0.5);
  vec3 d = normalize(vec3(aPos.x * t * uAspect, aPos.y * t, -1.0));
  float cp = cos(uPitch), sp = sin(uPitch);
  d = vec3(d.x, cp * d.y - sp * d.z, sp * d.y + cp * d.z);
  float cy = cos(uYaw), sy = sin(uYaw);
  d = vec3(cy * d.x + sy * d.z, d.y, -sy * d.x + cy * d.z);
  vDir = d;
  gl_Position = vec4(aPos, 0.0, 1.0);
}
`

const FRAG_SRC = `
precision mediump float;
varying vec3 vDir;
uniform sampler2D uTex;
const float PI = 3.141592653589793;
void main() {
  vec3 d = normalize(vDir);
  float lon = atan(d.x, -d.z);
  float lat = asin(clamp(d.y, -1.0, 1.0));
  vec2 uv = vec2(lon / (2.0 * PI) + 0.5, 0.5 - lat / PI);
  gl_FragColor = texture2D(uTex, uv);
}
`

let gl: WebGLRenderingContext | null = null
let program: WebGLProgram | null = null
let texture: WebGLTexture | null = null
let uniforms: Record<string, WebGLUniformLocation | null> = {}
let buffer: WebGLBuffer | null = null
let observer: ResizeObserver | null = null
let frame = 0
let disposed = false

let yaw = 0
let pitch = 0
let fov = 1.35
let dragging = false
let lastX = 0
let lastY = 0

function compile(source: string, type: number): WebGLShader | null {
  if (!gl) return null
  const shader = gl.createShader(type)
  if (!shader) return null
  gl.shaderSource(shader, source)
  gl.compileShader(shader)
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    error.value = `着色器编译失败：${gl.getShaderInfoLog(shader) ?? ''}`
    gl.deleteShader(shader)
    return null
  }
  return shader
}

function initGl(): boolean {
  const el = canvas.value
  if (!el) return false
  gl = (el.getContext('webgl') || el.getContext('experimental-webgl')) as WebGLRenderingContext | null
  if (!gl) {
    error.value = '当前浏览器不支持 WebGL，无法查看全景'
    return false
  }
  const vs = compile(VERT_SRC, gl.VERTEX_SHADER)
  const fs = compile(FRAG_SRC, gl.FRAGMENT_SHADER)
  if (!vs || !fs) return false
  program = gl.createProgram()
  if (!program) return false
  gl.attachShader(program, vs)
  gl.attachShader(program, fs)
  gl.linkProgram(program)
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    error.value = '全景着色器链接失败'
    return false
  }
  gl.useProgram(program)

  buffer = gl.createBuffer()
  gl.bindBuffer(gl.ARRAY_BUFFER, buffer)
  gl.bufferData(
    gl.ARRAY_BUFFER,
    new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]),
    gl.STATIC_DRAW,
  )
  const aPos = gl.getAttribLocation(program, 'aPos')
  gl.enableVertexAttribArray(aPos)
  gl.vertexAttribPointer(aPos, 2, gl.FLOAT, false, 0, 0)

  uniforms = {
    uFov: gl.getUniformLocation(program, 'uFov'),
    uAspect: gl.getUniformLocation(program, 'uAspect'),
    uYaw: gl.getUniformLocation(program, 'uYaw'),
    uPitch: gl.getUniformLocation(program, 'uPitch'),
    uTex: gl.getUniformLocation(program, 'uTex'),
  }
  gl.uniform1i(uniforms.uTex, 0)

  texture = gl.createTexture()
  gl.activeTexture(gl.TEXTURE0)
  gl.bindTexture(gl.TEXTURE_2D, texture)
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE)
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE)
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR)
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR)
  return true
}

function resize(): void {
  const el = canvas.value
  if (!el || !gl) return
  const dpr = window.devicePixelRatio || 1
  const width = Math.max(el.clientWidth, 1)
  const height = Math.max(el.clientHeight, 1)
  el.width = Math.round(width * dpr)
  el.height = Math.round(height * dpr)
  gl.viewport(0, 0, el.width, el.height)
  scheduleDraw()
}

function scheduleDraw(): void {
  if (frame || disposed) return
  frame = window.requestAnimationFrame(() => {
    frame = 0
    draw()
  })
}

function draw(): void {
  if (!gl || !program || !canvas.value) return
  const el = canvas.value
  if (gl.isContextLost?.()) return
  gl.clearColor(0.05, 0.07, 0.1, 1)
  gl.clear(gl.COLOR_BUFFER_BIT)
  gl.useProgram(program)
  gl.uniform1f(uniforms.uFov, fov)
  gl.uniform1f(uniforms.uAspect, el.width / Math.max(el.height, 1))
  gl.uniform1f(uniforms.uYaw, yaw)
  gl.uniform1f(uniforms.uPitch, pitch)
  gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4)
}

function loadTexture(src: string): void {
  if (!gl || !texture) return
  loading.value = true
  error.value = ''
  const img = new Image()
  img.crossOrigin = 'anonymous'
  img.onload = () => {
    if (!gl || !texture || disposed) return
    const maxSize = gl.getParameter(gl.MAX_TEXTURE_SIZE) as number
    let source: TexImageSource = img
    // 超大分辨率全景图先降采样，避免超出显卡纹理上限
    if (img.width > maxSize || img.height > maxSize) {
      const ratio = Math.min(maxSize / img.width, maxSize / img.height)
      const off = document.createElement('canvas')
      off.width = Math.max(1, Math.floor(img.width * ratio))
      off.height = Math.max(1, Math.floor(img.height * ratio))
      const ctx = off.getContext('2d')
      if (ctx) {
        ctx.drawImage(img, 0, 0, off.width, off.height)
        source = off
      }
    }
    gl.bindTexture(gl.TEXTURE_2D, texture)
    // 等距柱状投影：图像顶部对应天顶，WebGL 未翻转即可匹配 v=0 在上
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false)
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, source)
    loading.value = false
    resize()
  }
  img.onerror = () => {
    loading.value = false
    error.value = '全景图加载失败'
  }
  img.src = src
}

function onPointerDown(e: PointerEvent): void {
  dragging = true
  lastX = e.clientX
  lastY = e.clientY
  ;(e.target as HTMLElement).setPointerCapture?.(e.pointerId)
}

function onPointerMove(e: PointerEvent): void {
  if (!dragging) return
  const el = canvas.value
  if (!el) return
  const dx = e.clientX - lastX
  const dy = e.clientY - lastY
  lastX = e.clientX
  lastY = e.clientY
  const scale = fov / Math.max(el.clientHeight, 1)
  yaw -= dx * scale
  pitch = Math.max(-1.45, Math.min(1.45, pitch + dy * scale))
  scheduleDraw()
}

function onPointerUp(): void {
  dragging = false
}

function onWheel(e: WheelEvent): void {
  e.preventDefault()
  fov = Math.max(0.35, Math.min(2.2, fov * Math.exp(e.deltaY * 0.001)))
  scheduleDraw()
}

function reset(): void {
  yaw = 0
  pitch = 0
  fov = 1.35
  scheduleDraw()
}

function teardown(): void {
  disposed = true
  observer?.disconnect()
  observer = null
  if (frame) window.cancelAnimationFrame(frame)
  frame = 0
  const el = canvas.value
  if (el) {
    el.removeEventListener('pointerdown', onPointerDown)
    el.removeEventListener('pointermove', onPointerMove)
    el.removeEventListener('pointerup', onPointerUp)
    el.removeEventListener('pointerleave', onPointerUp)
    el.removeEventListener('dblclick', reset)
    el.removeEventListener('wheel', onWheel)
  }
  if (gl) {
    if (texture) gl.deleteTexture(texture)
    if (buffer) gl.deleteBuffer(buffer)
    if (program) gl.deleteProgram(program)
  }
  gl = null
  program = null
  texture = null
  buffer = null
}

onMounted(() => {
  if (!initGl()) {
    loading.value = false
    return
  }
  const el = canvas.value!
  el.addEventListener('pointerdown', onPointerDown)
  el.addEventListener('pointermove', onPointerMove)
  el.addEventListener('pointerup', onPointerUp)
  el.addEventListener('pointerleave', onPointerUp)
  el.addEventListener('dblclick', reset)
  el.addEventListener('wheel', onWheel, { passive: false })
  observer = new ResizeObserver(() => resize())
  observer.observe(el)
  loadTexture(props.src)
})

watch(
  () => props.src,
  (next) => {
    if (next && gl) loadTexture(next)
  },
)

onBeforeUnmount(teardown)
</script>

<style scoped>
.pano {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 320px;
  background: #0b0f16;
  border-radius: 6px;
  overflow: hidden;
}

.pano-canvas {
  display: block;
  width: 100%;
  height: 100%;
  cursor: grab;
  touch-action: none;
}

.pano-canvas:active {
  cursor: grabbing;
}

.pano-mask {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #cbd5e1;
  font-size: 13px;
  background: rgba(11, 15, 22, 0.75);
  pointer-events: none;
}

.pano-tip {
  position: absolute;
  left: 12px;
  bottom: 10px;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 12px;
  color: #e2e8f0;
  background: rgba(15, 23, 42, 0.55);
  pointer-events: none;
}
</style>
