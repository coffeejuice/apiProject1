import { useEffect, useRef } from 'react'

import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { mergeVertices } from 'three/examples/jsm/utils/BufferGeometryUtils.js'

import type { SimulationStepSurfaceMesh } from '../../types/api'

const SHARP_EDGE_THRESHOLD_DEG = 30
const VERTEX_MERGE_TOLERANCE = 1e-4
const YAW_ROTATE_RADIANS_PER_PIXEL = 0.004
const PITCH_ROTATE_RADIANS_PER_PIXEL = 0.0028
const AXIS_TRIAD_CENTER = 36
const AXIS_TRIAD_LENGTH = 24
const DEFAULT_CAMERA_FILL_RATIO = 0.82

interface SurfaceViewState {
  groupQuaternion: [number, number, number, number]
  cameraDirection: [number, number, number]
  distanceFactor: number
  targetOffsetFactor: [number, number, number]
}

let rememberedSurfaceViewState: SurfaceViewState | null = null

export interface SurfaceMeshLayer {
  key: string
  surface?: SimulationStepSurfaceMesh | null
  color: string
  opacity: number
  edgeOpacity?: number
  sharpEdgeOpacity?: number
}

function asFiniteNumber(value: unknown): number | null {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : null
}

function buildSurfaceGeometry(surface: SimulationStepSurfaceMesh): THREE.BufferGeometry | null {
  const vertexIndexMap = new Map<number, number>()
  const positions: number[] = []

  surface.vertices.forEach((vertex, sourceIndex) => {
    if (!Array.isArray(vertex) || vertex.length < 3) {
      return
    }
    const x = asFiniteNumber(vertex[0])
    const y = asFiniteNumber(vertex[1])
    const z = asFiniteNumber(vertex[2])
    if (x === null || y === null || z === null) {
      return
    }
    vertexIndexMap.set(sourceIndex, positions.length / 3)
    positions.push(x, y, z)
  })

  if (positions.length === 0) {
    return null
  }

  const indices: number[] = []
  surface.faces.forEach((face) => {
    if (!Array.isArray(face) || face.length < 3) {
      return
    }
    const mappedFace = face
      .map((sourceIndex) => Number.isInteger(sourceIndex) ? vertexIndexMap.get(sourceIndex) : undefined)
      .filter((index): index is number => index !== undefined)
    if (mappedFace.length < 3) {
      return
    }
    const first = mappedFace[0]
    for (let index = 1; index < mappedFace.length - 1; index += 1) {
      indices.push(first, mappedFace[index], mappedFace[index + 1])
    }
  })

  if (indices.length === 0) {
    return null
  }

  const geometry = new THREE.BufferGeometry()
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3))
  geometry.setIndex(indices)
  geometry.computeVertexNormals()
  geometry.computeBoundingBox()
  geometry.computeBoundingSphere()
  return geometry
}

function boundsFrame(box: THREE.Box3): { center: THREE.Vector3; radius: number } {
  const sphere = box.getBoundingSphere(new THREE.Sphere())
  return {
    center: sphere.center.clone(),
    radius: Math.max(sphere.radius, 0.001),
  }
}

function setCameraClipPlanes(camera: THREE.PerspectiveCamera, distance: number, radius: number) {
  camera.near = Math.max(distance - radius * 5, 0.01)
  camera.far = Math.max(distance + radius * 24, distance + 100)
  camera.updateProjectionMatrix()
}

function fitCameraToObject({
  camera,
  controls,
  box,
  width,
  height,
}: {
  camera: THREE.PerspectiveCamera
  controls: OrbitControls
  box: THREE.Box3
  width: number
  height: number
}) {
  const { center, radius } = boundsFrame(box)
  const halfFovRadians = THREE.MathUtils.degToRad(camera.fov * 0.5)
  const aspect = Math.max(width / Math.max(height, 1), 0.1)
  const fitByHeight = radius / Math.tan(halfFovRadians)
  const fitByWidth = fitByHeight / aspect
  const fitDistance = Math.max(fitByHeight, fitByWidth) / DEFAULT_CAMERA_FILL_RATIO
  const isometricDirection = new THREE.Vector3(1.35, -1.15, 0.9).normalize()

  camera.up.set(0, 0, 1)
  camera.position.copy(center).addScaledVector(isometricDirection, fitDistance)
  setCameraClipPlanes(camera, fitDistance, radius)
  camera.lookAt(center)

  controls.target.copy(center)
  controls.update()
}

function captureSurfaceViewState({
  group,
  camera,
  controls,
  box,
}: {
  group: THREE.Group
  camera: THREE.PerspectiveCamera
  controls: OrbitControls
  box: THREE.Box3
}): SurfaceViewState {
  const { center, radius } = boundsFrame(box)
  const cameraOffset = camera.position.clone().sub(controls.target)
  const cameraDistance = Math.max(cameraOffset.length(), 0.001)
  const cameraDirection = cameraOffset.normalize()
  const targetOffset = controls.target.clone().sub(center).divideScalar(radius)
  return {
    groupQuaternion: group.quaternion.toArray(),
    cameraDirection: cameraDirection.toArray(),
    distanceFactor: cameraDistance / radius,
    targetOffsetFactor: targetOffset.toArray(),
  }
}

function applySurfaceViewState({
  state,
  group,
  camera,
  controls,
  box,
}: {
  state: SurfaceViewState
  group: THREE.Group
  camera: THREE.PerspectiveCamera
  controls: OrbitControls
  box: THREE.Box3
}) {
  const { center, radius } = boundsFrame(box)
  const target = new THREE.Vector3(...state.targetOffsetFactor).multiplyScalar(radius).add(center)
  const direction = new THREE.Vector3(...state.cameraDirection).normalize()
  const distance = Math.max(radius * state.distanceFactor, radius * 0.25)

  group.quaternion.fromArray(state.groupQuaternion)
  controls.target.copy(target)
  camera.position.copy(target).addScaledVector(direction, distance)
  camera.up.set(0, 0, 1)
  setCameraClipPlanes(camera, distance, radius)
  camera.lookAt(target)
  controls.update()
}

function disposeObject3D(object: THREE.Object3D) {
  const geometries = new Set<THREE.BufferGeometry>()
  const materials = new Set<THREE.Material>()
  object.traverse((child) => {
    if (child instanceof THREE.Mesh || child instanceof THREE.LineSegments) {
      geometries.add(child.geometry)
      const material = child.material
      if (Array.isArray(material)) {
        material.forEach((item) => materials.add(item))
      } else {
        materials.add(material)
      }
    }
  })
  geometries.forEach((geometry) => geometry.dispose())
  materials.forEach((material) => material.dispose())
}

export default function SurfaceMeshThreeView({
  layers,
  isLoading = false,
  emptyMessage = 'Surface mesh is unavailable',
  className = '',
}: {
  layers: SurfaceMeshLayer[]
  isLoading?: boolean
  emptyMessage?: string
  className?: string
}) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const xAxisLineRef = useRef<SVGLineElement | null>(null)
  const yAxisLineRef = useRef<SVGLineElement | null>(null)
  const zAxisLineRef = useRef<SVGLineElement | null>(null)
  const xAxisLabelRef = useRef<SVGTextElement | null>(null)
  const yAxisLabelRef = useRef<SVGTextElement | null>(null)
  const zAxisLabelRef = useRef<SVGTextElement | null>(null)
  const resetViewRef = useRef<(() => void) | null>(null)

  useEffect(() => {
    const container = containerRef.current
    if (!container) {
      return
    }

    const activeLayers = layers.filter((layer) => layer.surface)
    if (activeLayers.length === 0) {
      container.replaceChildren()
      return
    }

    const scene = new THREE.Scene()
    scene.background = new THREE.Color('#faf9f7')

    const camera = new THREE.PerspectiveCamera(35, 1, 0.01, 100000)
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))
    renderer.outputColorSpace = THREE.SRGBColorSpace
    renderer.domElement.style.width = '100%'
    renderer.domElement.style.height = '100%'
    renderer.domElement.style.display = 'block'
    container.replaceChildren(renderer.domElement)

    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = false
    controls.enablePan = true
    controls.enableRotate = false
    controls.enableZoom = true

    const ambientLight = new THREE.AmbientLight(0xffffff, 0.78)
    const keyLight = new THREE.DirectionalLight(0xffffff, 0.92)
    keyLight.position.set(1.4, -1.1, 2.2)
    scene.add(ambientLight, keyLight)

    const group = new THREE.Group()
    const bounds = new THREE.Box3()

    activeLayers.forEach((layer, layerIndex) => {
      if (!layer.surface) {
        return
      }
      const geometry = buildSurfaceGeometry(layer.surface)
      if (!geometry) {
        return
      }

      const surfaceMaterial = new THREE.MeshStandardMaterial({
        color: new THREE.Color(layer.color),
        transparent: true,
        opacity: layer.opacity,
        roughness: 0.72,
        metalness: 0.04,
        side: THREE.DoubleSide,
        depthWrite: layer.opacity >= 0.95,
        polygonOffset: true,
        polygonOffsetFactor: 1 + layerIndex,
        polygonOffsetUnits: 1,
      })
      const mesh = new THREE.Mesh(geometry, surfaceMaterial)
      mesh.renderOrder = layerIndex * 10
      group.add(mesh)

      const wireframeMaterial = new THREE.MeshBasicMaterial({
        color: new THREE.Color(layer.color),
        wireframe: true,
        transparent: true,
        opacity: layer.edgeOpacity ?? 0.13,
        depthWrite: false,
      })
      const wireframe = new THREE.Mesh(geometry, wireframeMaterial)
      wireframe.renderOrder = layerIndex * 10 + 1
      group.add(wireframe)

      const mergedGeometry = mergeVertices(geometry.clone(), VERTEX_MERGE_TOLERANCE)
      const sharpEdgesGeometry = new THREE.EdgesGeometry(mergedGeometry, SHARP_EDGE_THRESHOLD_DEG)
      mergedGeometry.dispose()
      const sharpEdgesMaterial = new THREE.LineBasicMaterial({
        color: new THREE.Color(layer.color),
        transparent: true,
        opacity: layer.sharpEdgeOpacity ?? 0.85,
        depthWrite: false,
      })
      const sharpEdges = new THREE.LineSegments(sharpEdgesGeometry, sharpEdgesMaterial)
      sharpEdges.renderOrder = layerIndex * 10 + 2
      group.add(sharpEdges)

      geometry.computeBoundingBox()
      if (geometry.boundingBox) {
        bounds.union(geometry.boundingBox)
      }
    })

    if (group.children.length === 0 || bounds.isEmpty()) {
      disposeObject3D(group)
      controls.dispose()
      renderer.dispose()
      container.replaceChildren()
      return
    }

    scene.add(group)

    let animationFrameId: number | null = null
    let activeRotatePointerId: number | null = null
    let previousPointerX = 0
    let previousPointerY = 0
    let suppressViewRemembering = false
    const axisScratch = new THREE.Vector3()
    const cameraViewMatrix = new THREE.Matrix4()
    const updateAxisTriad = () => {
      cameraViewMatrix.copy(camera.matrixWorldInverse)

      const updateAxis = (
        axis: THREE.Vector3,
        line: SVGLineElement | null,
        label: SVGTextElement | null
      ) => {
        if (!line || !label) {
          return
        }
        axisScratch.copy(axis).applyQuaternion(group.quaternion).transformDirection(cameraViewMatrix)
        const projectedLength = Math.hypot(axisScratch.x, axisScratch.y)
        const length = AXIS_TRIAD_LENGTH * Math.max(0.45, Math.min(projectedLength, 1))
        const x2 = AXIS_TRIAD_CENTER + axisScratch.x * length
        const y2 = AXIS_TRIAD_CENTER - axisScratch.y * length
        const labelX = AXIS_TRIAD_CENTER + axisScratch.x * (length + 8)
        const labelY = AXIS_TRIAD_CENTER - axisScratch.y * (length + 8)
        const opacity = String(0.48 + Math.max(projectedLength, 0.25) * 0.48)

        line.setAttribute('x1', String(AXIS_TRIAD_CENTER))
        line.setAttribute('y1', String(AXIS_TRIAD_CENTER))
        line.setAttribute('x2', x2.toFixed(2))
        line.setAttribute('y2', y2.toFixed(2))
        line.setAttribute('opacity', opacity)
        label.setAttribute('x', labelX.toFixed(2))
        label.setAttribute('y', labelY.toFixed(2))
        label.setAttribute('opacity', opacity)
      }

      updateAxis(new THREE.Vector3(1, 0, 0), xAxisLineRef.current, xAxisLabelRef.current)
      updateAxis(new THREE.Vector3(0, 1, 0), yAxisLineRef.current, yAxisLabelRef.current)
      updateAxis(new THREE.Vector3(0, 0, 1), zAxisLineRef.current, zAxisLabelRef.current)
    }
    const renderScene = () => {
      updateAxisTriad()
      renderer.render(scene, camera)
    }
    const animateScene = () => {
      controls.update()
      renderScene()
      animationFrameId = window.requestAnimationFrame(animateScene)
    }

    const rememberCurrentView = () => {
      rememberedSurfaceViewState = captureSurfaceViewState({ group, camera, controls, box: bounds })
    }
    const handleControlsChange = () => {
      if (!suppressViewRemembering) {
        rememberCurrentView()
      }
      renderScene()
    }

    controls.addEventListener('change', handleControlsChange)

    const handleRotatePointerDown = (event: PointerEvent) => {
      if (event.button !== 0 || event.pointerType !== 'mouse') {
        return
      }
      event.preventDefault()
      event.stopPropagation()
      activeRotatePointerId = event.pointerId
      previousPointerX = event.clientX
      previousPointerY = event.clientY
      renderer.domElement.setPointerCapture(event.pointerId)
      renderer.domElement.style.cursor = 'grabbing'
    }

    const handleRotatePointerMove = (event: PointerEvent) => {
      if (activeRotatePointerId !== event.pointerId) {
        return
      }
      event.preventDefault()
      event.stopPropagation()
      const deltaX = event.clientX - previousPointerX
      const deltaY = event.clientY - previousPointerY
      previousPointerX = event.clientX
      previousPointerY = event.clientY

      if (deltaX !== 0) {
        group.rotateOnWorldAxis(new THREE.Vector3(0, 0, 1), deltaX * YAW_ROTATE_RADIANS_PER_PIXEL)
      }
      if (deltaY !== 0) {
        const cameraRight = new THREE.Vector3(1, 0, 0).applyQuaternion(camera.quaternion).normalize()
        group.rotateOnWorldAxis(cameraRight, deltaY * PITCH_ROTATE_RADIANS_PER_PIXEL)
      }
      rememberCurrentView()
      renderScene()
    }

    const handleRotatePointerEnd = (event: PointerEvent) => {
      if (activeRotatePointerId !== event.pointerId) {
        return
      }
      event.preventDefault()
      event.stopPropagation()
      activeRotatePointerId = null
      if (renderer.domElement.hasPointerCapture(event.pointerId)) {
        renderer.domElement.releasePointerCapture(event.pointerId)
      }
      renderer.domElement.style.cursor = 'grab'
    }

    renderer.domElement.style.cursor = 'grab'
    renderer.domElement.addEventListener('pointerdown', handleRotatePointerDown)
    renderer.domElement.addEventListener('pointermove', handleRotatePointerMove)
    renderer.domElement.addEventListener('pointerup', handleRotatePointerEnd)
    renderer.domElement.addEventListener('pointercancel', handleRotatePointerEnd)

    const resizeRenderer = () => {
      const width = Math.max(container.clientWidth, 1)
      const height = Math.max(container.clientHeight, 1)
      renderer.setSize(width, height, false)
      camera.aspect = width / height
      suppressViewRemembering = true
      fitCameraToObject({ camera, controls, box: bounds, width, height })
      if (rememberedSurfaceViewState) {
        applySurfaceViewState({
          state: rememberedSurfaceViewState,
          group,
          camera,
          controls,
          box: bounds,
        })
      }
      suppressViewRemembering = false
      rememberCurrentView()
      renderScene()
    }

    resetViewRef.current = () => {
      const width = Math.max(container.clientWidth, 1)
      const height = Math.max(container.clientHeight, 1)
      group.quaternion.identity()
      camera.aspect = width / height
      suppressViewRemembering = true
      fitCameraToObject({ camera, controls, box: bounds, width, height })
      suppressViewRemembering = false
      rememberCurrentView()
      renderScene()
    }

    const resizeObserver = new ResizeObserver(resizeRenderer)
    resizeObserver.observe(container)
    resizeRenderer()
    animateScene()

    return () => {
      if (animationFrameId !== null) {
        window.cancelAnimationFrame(animationFrameId)
      }
      renderer.domElement.removeEventListener('pointerdown', handleRotatePointerDown)
      renderer.domElement.removeEventListener('pointermove', handleRotatePointerMove)
      renderer.domElement.removeEventListener('pointerup', handleRotatePointerEnd)
      renderer.domElement.removeEventListener('pointercancel', handleRotatePointerEnd)
      resizeObserver.disconnect()
      controls.removeEventListener('change', handleControlsChange)
      controls.dispose()
      scene.remove(group)
      disposeObject3D(group)
      renderer.dispose()
      container.replaceChildren()
      resetViewRef.current = null
    }
  }, [layers])

  const hasMesh = layers.some((layer) => layer.surface)

  return (
    <div className={`relative overflow-hidden rounded-lg bg-[#faf9f7] ${className}`}>
      <div
        ref={containerRef}
        className="h-full w-full"
        onClick={(event) => event.stopPropagation()}
        onPointerDown={(event) => event.stopPropagation()}
        onWheel={(event) => event.stopPropagation()}
      />
      {hasMesh ? (
        <button
          type="button"
          title="Reset view"
          aria-label="Reset 3D view"
          className="absolute left-2 top-2 inline-flex h-7 w-7 items-center justify-center rounded-lg border border-[rgba(55,53,47,0.12)] bg-white/78 text-[rgba(55,53,47,0.62)] shadow-sm backdrop-blur transition hover:bg-white hover:text-[rgba(55,53,47,0.88)]"
          onClick={(event) => {
            event.preventDefault()
            event.stopPropagation()
            resetViewRef.current?.()
          }}
          onPointerDown={(event) => {
            event.stopPropagation()
          }}
        >
          <svg viewBox="0 0 20 20" className="h-[18px] w-[18px]" fill="none" aria-hidden="true">
            <path
              d="M15.2 7.2A5.9 5.9 0 0 0 4.6 6M4.4 3.8V6.8H7.4"
              stroke="currentColor"
              strokeWidth="1.7"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <path
              d="M4.8 12.8A5.9 5.9 0 0 0 15.4 14M15.6 16.2V13.2H12.6"
              stroke="currentColor"
              strokeWidth="1.7"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      ) : null}
      {hasMesh ? (
        <svg
          viewBox="0 0 72 72"
          className="pointer-events-none absolute right-2 top-2 h-[72px] w-[72px] rounded-xl border border-[rgba(55,53,47,0.10)] bg-white/70 shadow-sm backdrop-blur"
          aria-hidden="true"
        >
          <circle cx={AXIS_TRIAD_CENTER} cy={AXIS_TRIAD_CENTER} r="2.2" fill="rgba(55,53,47,0.48)" />
          <line ref={xAxisLineRef} stroke="#dc2626" strokeWidth="2.2" strokeLinecap="round" />
          <line ref={yAxisLineRef} stroke="#16a34a" strokeWidth="2.2" strokeLinecap="round" />
          <line ref={zAxisLineRef} stroke="#2563eb" strokeWidth="2.2" strokeLinecap="round" />
          <text ref={xAxisLabelRef} fill="#b91c1c" fontSize="10" fontWeight="700" textAnchor="middle" dominantBaseline="central">X</text>
          <text ref={yAxisLabelRef} fill="#15803d" fontSize="10" fontWeight="700" textAnchor="middle" dominantBaseline="central">Y</text>
          <text ref={zAxisLabelRef} fill="#1d4ed8" fontSize="10" fontWeight="700" textAnchor="middle" dominantBaseline="central">Z</text>
        </svg>
      ) : null}
      {!hasMesh ? (
        <div className="absolute inset-0 flex items-center justify-center px-4 text-center font-mono text-[10px] text-[rgba(55,53,47,0.45)]">
          {isLoading ? 'Loading surface mesh...' : emptyMessage}
        </div>
      ) : null}
    </div>
  )
}
