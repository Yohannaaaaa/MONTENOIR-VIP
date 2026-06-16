console.log("METROPOLY 3D ENGINE OK");

let scene, camera, renderer;

function init3D(){
    const canvas = document.getElementById("threeCanvas");

    scene = new THREE.Scene();
    scene.background = new THREE.Color("#050505");

    camera = new THREE.PerspectiveCamera(
        45,
        window.innerWidth / window.innerHeight,
        0.1,
        100
    );

    camera.position.set(0, 30, 0.01);
    camera.lookAt(0, 0, 0);

    renderer = new THREE.WebGLRenderer({
        canvas: canvas,
        antialias: true
    });

    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(window.devicePixelRatio || 1);

    const light = new THREE.AmbientLight(0xffffff, 1.8);
    scene.add(light);

    const boardTexture = new THREE.TextureLoader().load(
        "/static/metroploy_plateau_lux.png.png"
    );

    boardTexture.colorSpace = THREE.SRGBColorSpace;

    const board = new THREE.Mesh(
        new THREE.BoxGeometry(11.5, 0.18, 7.8),
        new THREE.MeshStandardMaterial({
            map: boardTexture,
            roughness: 0.35,
            metalness: 0.1
        })
    );

    scene.add(board);

    const table = new THREE.Mesh(
        new THREE.BoxGeometry(12.8, 0.25, 9),
        new THREE.MeshStandardMaterial({
            color: "#120900",
            roughness: 0.45,
            metalness: 0.2
        })
    );

    table.position.y = -0.25;
    scene.add(table);

    animate();
}

function animate(){
    requestAnimationFrame(animate);
    renderer.render(scene, camera);
}

window.addEventListener("resize", () => {
    if(!camera || !renderer) return;

    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();

    renderer.setSize(window.innerWidth, window.innerHeight);
});

document.addEventListener("DOMContentLoaded", init3D);
