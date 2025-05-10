export async function delay(duration: number): Promise<{ message: string }> {
  const milliseconds = duration * 1000

  return new Promise((resolve) => {
    setTimeout(() => {
      resolve({
        message: `Completed delay of ${duration} ${
          duration === 1 ? "second" : "seconds"
        }`,
      })
    }, milliseconds)
  })
}
