import { Routes, Route, Navigate, Link } from "react-router-dom";
import Layout from "./components/Layout.jsx";
import { EmptyState } from "./components/ui.jsx";
import TeacherCourses from "./pages/TeacherCourses.jsx";
import TeacherCourse from "./pages/TeacherCourse.jsx";
import TeacherInsights from "./pages/TeacherInsights.jsx";
import StudentHome from "./pages/StudentHome.jsx";
import StudentAsk from "./pages/StudentAsk.jsx";

function NotFound() {
  return (
    <EmptyState
      icon="?"
      title="Page not found"
      message="That page does not exist."
      action={<Link className="btn btn-ghost btn-sm" to="/teacher">Go home</Link>}
    />
  );
}

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Navigate to="/teacher" replace />} />
        <Route path="/teacher" element={<TeacherCourses />} />
        <Route path="/teacher/courses/:courseId" element={<TeacherCourse />} />
        <Route path="/teacher/courses/:courseId/insights" element={<TeacherInsights />} />
        <Route path="/student" element={<StudentHome />} />
        <Route path="/student/courses/:courseId" element={<StudentAsk />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Layout>
  );
}
