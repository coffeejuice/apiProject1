import { type MouseEvent, useEffect, useMemo, useRef, useState } from 'react'

import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js'
import { mergeVertices } from 'three/examples/jsm/utils/BufferGeometryUtils.js'

import { apiClient } from '../../lib/apiClient'

type PreviewStatus = 'loading' | 'ready' | 'missing' | 'error'
const DEFAULT_DIE_STL_VISUAL_SHARP_EDGE_ANGLE_DEG = 15
const DEFAULT_DIE_STL_VISUAL_SURFACE_COLOR = '#d7e1ed'
const DEFAULT_DIE_STL_VISUAL_MESH_LINE_COLOR = '#e2e8f0'
const DEFAULT_DIE_STL_VISUAL_SHARP_EDGE_LINE_COLOR = '#334155'
const VERTEX_MERGE_TOLERANCE = 1e-4
const viteEnv = (
  import.meta as { env?: Record<string, string | boolean | undefined> }
).env

function resolveVisualNumberEnv(rawValue: unknown, fallback: number): number {
  const parsed = Number(rawValue)
  if (!Number.isFinite(parsed)) {
    return fallback
  }
  return parsed
}

function resolveVisualColorEnv(rawValue: unknown, fallback: string): string {
  if (typeof rawValue !== 'string') {
    return fallback
  }
  const normalized = rawValue.trim()
  return normalized || fallback
}

function resolveSharpEdgeAngleThresholdDegrees(): number {
  const rawValue = resolveVisualNumberEnv(
    viteEnv?.VITE_DIE_STL_VISUAL_SHARP_EDGE_ANGLE_DEG,
    DEFAULT_DIE_STL_VISUAL_SHARP_EDGE_ANGLE_DEG
  )
  return THREE.MathUtils.clamp(rawValue, 0, 180)
}

const DIE_STL_VISUAL = {
  surfaceColor: resolveVisualColorEnv(
    viteEnv?.VITE_DIE_STL_VISUAL_SURFACE_COLOR,
    DEFAULT_DIE_STL_VISUAL_SURFACE_COLOR
  ),
  meshLineColor: resolveVisualColorEnv(
    viteEnv?.VITE_DIE_STL_VISUAL_MESH_LINE_COLOR,
    DEFAULT_DIE_STL_VISUAL_MESH_LINE_COLOR
  ),
  sharpEdgeLineColor: resolveVisualColorEnv(
    viteEnv?.VITE_DIE_STL_VISUAL_SHARP_EDGE_LINE_COLOR,
    DEFAULT_DIE_STL_VISUAL_SHARP_EDGE_LINE_COLOR
  ),
  sharpEdgeAngleDeg: resolveSharpEdgeAngleThresholdDegrees(),
} as const

function buildAbsoluteAssetUrl(path: string): string {
  try {
    return new URL(path).toString()
  } catch {
    const baseUrl = apiClient.getBaseUrl()
    const normalizedBaseUrl = baseUrl.endsWith('/') ? baseUrl : `${baseUrl}/`
    return new URL(path, normalizedBaseUrl).toString()
  }
}

export default function DieStlPreview({
  stlFileUrl,
  stlFileExists = false,
  className = '',
}: {
  stlFileUrl?: string | null
  stlFileExists?: boolean
  className?: string
}) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const controlsRef = useRef<OrbitControls | null>(null)
  const sceneRef = useRef<THREE.Scene | null>(null)
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null)
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null)
  const initialCameraPositionRef = useRef<THREE.Vector3 | null>(null)
  const initialCameraTargetRef = useRef<THREE.Vector3 | null>(null)

  const [status, setStatus] = useState<PreviewStatus>(stlFileUrl && stlFileExists ? 'loading' : 'missing')

  const stlUrl = useMemo(() => {
    if (!stlFileUrl) {
      return null
    }
    return buildAbsoluteAssetUrl(stlFileUrl)
  }, [stlFileUrl])

  useEffect(() => {
    const container = containerRef.current
    if (!container) {
      return
    }

    if (!stlUrl || !stlFileExists) {
      setStatus('missing')
      if (container.childElementCount > 0) {
        container.replaceChildren()
      }
      return
    }

    setStatus('loading')

    const scene = new THREE.Scene()
    scene.background = new THREE.Color('#f8fafc')
    sceneRef.current = scene

    const camera = new THREE.PerspectiveCamera(45, 1, 0.01, 100000)
    camera.up.set(0, 0, 1)
    cameraRef.current = camera

    const renderer = new THREE.WebGLRenderer({ antialias: true })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))
    renderer.outputColorSpace = THREE.SRGBColorSpace
    renderer.domElement.style.width = '100%'
    renderer.domElement.style.height = '100%'
    renderer.domElement.style.display = 'block'
    rendererRef.current = renderer

    container.replaceChildren(renderer.domElement)

    const ambientLight = new THREE.AmbientLight(0xffffff, 0.7)
    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.9)
    directionalLight.position.set(1, 1, 2)
    scene.add(ambientLight, directionalLight)

    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = false
    controls.enablePan = true
    controls.enableRotate = true
    controls.enableZoom = true
    controlsRef.current = controls

    const renderScene = () => {
      renderer.render(scene, camera)
    }

    controls.addEventListener('change', renderScene)

    const resizeRenderer = () => {
      const width = Math.max(container.clientWidth, 1)
      const height = Math.max(container.clientHeight, 1)
      renderer.setSize(width, height, false)
      camera.aspect = width / height
      camera.updateProjectionMatrix()
    }

    resizeRenderer()

    const resizeObserver = new ResizeObserver(() => {
      resizeRenderer()
      renderScene()
    })
    resizeObserver.observe(container)

    let disposed = false
    let mesh: THREE.Mesh<THREE.BufferGeometry, THREE.MeshStandardMaterial> | null = null
    let wireframeMesh: THREE.Mesh<THREE.BufferGeometry, THREE.MeshBasicMaterial> | null = null
    let sharpEdges: THREE.LineSegments<THREE.EdgesGeometry, THREE.LineBasicMaterial> | null = null
    const loader = new STLLoader()
    const token = apiClient.getToken()
    if (token) {
      loader.setRequestHeader({ Authorization: `Bearer ${token}` })
    }

    loader.load(
      stlUrl,
      (geometry) => {
        if (disposed) {
          geometry.dispose()
          return
        }

        geometry.computeBoundingBox()
        geometry.computeVertexNormals()

        const material = new THREE.MeshStandardMaterial({
          color: DIE_STL_VISUAL.surfaceColor,
          metalness: 0.1,
          roughness: 0.7,
          polygonOffset: true,
          polygonOffsetFactor: 1,
          polygonOffsetUnits: 1,
        })

        mesh = new THREE.Mesh(geometry, material)
        scene.add(mesh)

        const wireframeMaterial = new THREE.MeshBasicMaterial({
          color: DIE_STL_VISUAL.meshLineColor,
          wireframe: true,
          transparent: true,
          opacity: 0.32,
          depthTest: true,
          depthWrite: false,
        })
        wireframeMesh = new THREE.Mesh(geometry, wireframeMaterial)
        wireframeMesh.renderOrder = 1
        scene.add(wireframeMesh)

        const mergedGeometry = mergeVertices(geometry.clone(), VERTEX_MERGE_TOLERANCE)
        const sharpEdgesGeometry = new THREE.EdgesGeometry(mergedGeometry, DIE_STL_VISUAL.sharpEdgeAngleDeg)
        mergedGeometry.dispose()
        const sharpEdgesMaterial = new THREE.LineBasicMaterial({
          color: DIE_STL_VISUAL.sharpEdgeLineColor,
          transparent: true,
          opacity: 0.95,
          depthTest: true,
          depthWrite: false,
        })
        sharpEdges = new THREE.LineSegments(sharpEdgesGeometry, sharpEdgesMaterial)
        sharpEdges.renderOrder = 2
        scene.add(sharpEdges)

        const box = geometry.boundingBox ? geometry.boundingBox.clone() : new THREE.Box3().setFromObject(mesh)
        const sphere = box.getBoundingSphere(new THREE.Sphere())
        const center = sphere.center.clone()
        const radius = Math.max(sphere.radius, 0.001)
        const halfFovRadians = THREE.MathUtils.degToRad(camera.fov * 0.5)
        const fillRatio = 0.9
        const fitDistance = radius / (Math.tan(halfFovRadians) * fillRatio)
        const isometricDirection = new THREE.Vector3(1, 1, 1).normalize()

        camera.position.copy(center).addScaledVector(isometricDirection, fitDistance)
        camera.near = Math.max(fitDistance - radius * 4, 0.01)
        camera.far = Math.max(fitDistance + radius * 20, fitDistance + 100)
        camera.lookAt(center)
        camera.updateProjectionMatrix()

        controls.target.copy(center)
        controls.update()

        initialCameraPositionRef.current = camera.position.clone()
        initialCameraTargetRef.current = controls.target.clone()

        setStatus('ready')
        renderScene()
      },
      undefined,
      () => {
        if (disposed) {
          return
        }
        setStatus('error')
      }
    )

    return () => {
      disposed = true
      resizeObserver.disconnect()
      controls.removeEventListener('change', renderScene)
      controls.dispose()
      controlsRef.current = null

      if (mesh) {
        scene.remove(mesh)
        mesh.geometry.dispose()
        mesh.material.dispose()
      }
      if (wireframeMesh) {
        scene.remove(wireframeMesh)
        wireframeMesh.material.dispose()
      }
      if (sharpEdges) {
        scene.remove(sharpEdges)
        sharpEdges.geometry.dispose()
        sharpEdges.material.dispose()
      }

      renderer.dispose()
      rendererRef.current = null
      sceneRef.current = null
      cameraRef.current = null
      initialCameraPositionRef.current = null
      initialCameraTargetRef.current = null

      if (container.childElementCount > 0) {
        container.replaceChildren()
      }
    }
  }, [stlFileExists, stlUrl])

  const handleResetView = (event: MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation()

    const controls = controlsRef.current
    const scene = sceneRef.current
    const camera = cameraRef.current
    const renderer = rendererRef.current
    const initialPosition = initialCameraPositionRef.current
    const initialTarget = initialCameraTargetRef.current

    if (!controls || !scene || !camera || !renderer || !initialPosition || !initialTarget) {
      return
    }

    camera.position.copy(initialPosition)
    controls.target.copy(initialTarget)
    controls.update()
    renderer.render(scene, camera)
  }

  return (
    <div
      className={`relative h-full w-full ${className}`}
      onClick={(event) => event.stopPropagation()}
      onPointerDown={(event) => event.stopPropagation()}
      onWheel={(event) => event.stopPropagation()}
    >
      <div ref={containerRef} className="h-full w-full rounded border border-gray-200 bg-slate-50 overflow-hidden" />
      <div className="absolute top-1 right-1">
        <button type="button" className="ui-btn" onClick={handleResetView} disabled={status !== 'ready'}>
          Reset
        </button>
      </div>

      {status === 'loading' && (
        <div className="absolute bottom-1 left-1 right-1 text-center text-xs text-gray-600 bg-white/80 rounded px-1 py-0.5">
          Loading STL preview...
        </div>
      )}
      {status === 'missing' && (
        <div className="absolute bottom-1 left-1 right-1 text-center text-xs text-gray-600 bg-white/80 rounded px-1 py-0.5">
          {stlFileExists ? 'STL preview is not configured.' : 'STL file not found for this die.'}
        </div>
      )}
      {status === 'error' && (
        <div className="absolute bottom-1 left-1 right-1 text-center text-xs text-red-700 bg-red-50/90 rounded px-1 py-0.5">
          Failed to load STL preview.
        </div>
      )}
    </div>
  )
}
