import { initializeApp } from "firebase/app";
import { getAuth, GoogleAuthProvider } from "firebase/auth";

const firebaseConfig = {
  apiKey: "AIzaSyDcw68nLZN2FNCIHPUcZXJlXgQ7iyzLv4Y",
  authDomain: "voyageai-702fe.firebaseapp.com",
  projectId: "voyageai-702fe",
  storageBucket: "voyageai-702fe.firebasestorage.app",
  messagingSenderId: "146614734627",
  appId: "1:146614734627:web:183968ccb99b9e3b288696"
};

const app = initializeApp(firebaseConfig);

export const auth = getAuth(app);
export const googleProvider = new GoogleAuthProvider();