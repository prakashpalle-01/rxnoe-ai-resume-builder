import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowRight, Sparkles } from "lucide-react";
import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router-dom";
import { z } from "zod";
import { api } from "../lib/api";
import { Button, Card, Input } from "../components/ui";
import { useAppStore } from "../store/app-store";

const schema = z.object({
  email: z.string().email(),
  password: z.string().min(6)
});

type FormValues = z.infer<typeof schema>;

export function AuthPage({ mode }: { mode: "login" | "signup" }) {
  const navigate = useNavigate();
  const { setUserEmail } = useAppStore();
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<FormValues>({ resolver: zodResolver(schema) });

  async function onSubmit(values: FormValues) {
    const response = await api.post(`/auth/${mode}`, values);
    localStorage.setItem("rxnoe_token", response.data.access_token);
    localStorage.setItem("rxnoe_email", values.email);
    setUserEmail(values.email);
    navigate("/dashboard");
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-rx-soft px-4">
      <div className="w-full max-w-md">
        <div className="mb-6 flex items-center justify-center gap-3">
          <div className="flex size-11 items-center justify-center rounded-md bg-rx-blue text-white">
            <Sparkles size={20} />
          </div>
          <div>
            <h1 className="text-2xl font-bold">RxNoe</h1>
            <p className="text-sm text-rx-muted">AI Resume Builder</p>
          </div>
        </div>
        <Card title={mode === "login" ? "Welcome back" : "Create your workspace"}>
          <form className="space-y-4" onSubmit={handleSubmit(onSubmit)}>
            <label className="block text-sm font-medium">
              Email
              <Input className="mt-1" type="email" {...register("email")} />
              {errors.email && <span className="text-xs text-red-600">{errors.email.message}</span>}
            </label>
            <label className="block text-sm font-medium">
              Password
              <Input className="mt-1" type="password" {...register("password")} />
              {errors.password && <span className="text-xs text-red-600">{errors.password.message}</span>}
            </label>
            <Button className="w-full" disabled={isSubmitting}>
              {mode === "login" ? "Sign in" : "Sign up"}
              <ArrowRight size={17} />
            </Button>
          </form>
          <p className="mt-4 text-center text-sm text-rx-muted">
            {mode === "login" ? "Need an account?" : "Already have an account?"}{" "}
            <Link className="font-semibold text-rx-blue" to={mode === "login" ? "/signup" : "/login"}>
              {mode === "login" ? "Sign up" : "Sign in"}
            </Link>
          </p>
        </Card>
      </div>
    </main>
  );
}
