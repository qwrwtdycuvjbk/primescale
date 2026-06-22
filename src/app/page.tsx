import { Footer } from "@/components/Footer";
import { Header } from "@/components/Header";
import { Hero } from "@/components/Hero";
import { HowItWorks } from "@/components/HowItWorks";
import { PostRoleSection } from "@/components/PostRoleSection";
import { WhyUs } from "@/components/WhyUs";

export default function Home() {
  return (
    <>
      <Header />
      <main>
        <Hero />
        <HowItWorks />
        <WhyUs />
        <PostRoleSection />
      </main>
      <Footer />
    </>
  );
}
