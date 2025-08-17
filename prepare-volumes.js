const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const SYMLINK_PATH = path.join(__dirname, 'data');      // Path your app expects
const REAL_FOLDER = path.join(__dirname, 'real-data');  // Mounted folder

function copyFolder(src, dest) {
	try {
		fs.rmSync(dest, { recursive: true, force: true });
		fs.mkdirSync(dest, { recursive: true });
		fs.cpSync(src, dest, { recursive: true });
		console.log(`Copied ${src} → ${dest}`);
	} catch (err) {
		console.error(`Error copying folder: ${err}`);
		process.exit(1);
	}
}

if (fs.existsSync(REAL_FOLDER)) {
	copyFolder(REAL_FOLDER, SYMLINK_PATH);
} else {
	console.warn(`Real folder does not exist: ${REAL_FOLDER}`);
}

// Execute the main command
const args = process.argv.slice(2);
if (args.length > 0) {
	execSync(args.join(' '), { stdio: 'inherit' });
} else {
	console.warn('No command provided to start the app');
}
