# Android Testing Guidelines

## 框架選用準則

### MockK vs Mockito
- **優先使用 MockK**（Kotlin 專案）：原生支援 Kotlin suspend function、coroutines、data class、companion object
- Mockito 只在既有測試已使用時沿用，不混用兩者
- `@MockK`：一般 mock（預設嚴格驗證）
- `@RelaxedMockK`：不需一一設定 `every`，適合只驗證副作用的依賴
- `spyk(realObj)`：wrap 真實物件，只覆蓋部分行為

### JUnit4 vs JUnit5
- 依專案 `build.gradle` 已引入的版本沿用
- JUnit4：`@RunWith(JUnit4::class)`，rule 使用 `@get:Rule`
- JUnit5：`@ExtendWith(MockKExtension::class)`，使用 `@BeforeEach` / `@AfterEach`
- 混用時，JUnit5 需加 `junit-vintage-engine` 才能跑 JUnit4 測試

---

## Coroutines 測試 API

### 必用設定（JUnit4）
```kotlin
@get:Rule
val mainDispatcherRule = MainDispatcherRule()

// MainDispatcherRule 實作（若專案無）：
class MainDispatcherRule(
    val testDispatcher: TestCoroutineDispatcher = UnconfinedTestDispatcher()
) : TestWatcher() {
    override fun starting(description: Description) {
        Dispatchers.setMain(testDispatcher)
    }
    override fun finished(description: Description) {
        Dispatchers.resetMain()
    }
}
```

### runTest 基本用法
```kotlin
@Test
fun `fetchData_success_emitsResult`() = runTest {
    // given
    coEvery { repository.getData() } returns Result.success(mockData)
    // when
    viewModel.fetchData()
    // then
    assertEquals(UiState.Success(mockData), viewModel.uiState.value)
}
```

### UnconfinedTestDispatcher vs StandardTestDispatcher
- `UnconfinedTestDispatcher`：即時執行 coroutine，適合大多數 ViewModel 測試
- `StandardTestDispatcher`：需手動 `advanceUntilIdle()`，適合測試時序精確控制

---

## Flow 測試

### Turbine（推薦，需引入依賴）
```kotlin
@Test
fun `uiState_emitsLoadingThenSuccess`() = runTest {
    viewModel.uiState.test {
        assertEquals(UiState.Loading, awaitItem())
        assertEquals(UiState.Success(data), awaitItem())
        cancelAndIgnoreRemainingEvents()
    }
}
```

### 手動 collect（不需 Turbine）
```kotlin
@Test
fun `uiState_emitsCorrectSequence`() = runTest {
    val results = mutableListOf<UiState>()
    val job = launch(UnconfinedTestDispatcher()) {
        viewModel.uiState.toList(results)
    }
    viewModel.loadData()
    advanceUntilIdle()
    job.cancel()
    assertEquals(listOf(UiState.Loading, UiState.Success(data)), results)
}
```

---

## ViewModel 測試設定

### 必要的 Rule（JUnit4）
```kotlin
@get:Rule
val instantTaskExecutorRule = InstantTaskExecutorRule()  // 同步執行 LiveData
```

### ViewModel 建立方式
```kotlin
// 直接建立（手動注入依賴）
private lateinit var viewModel: UserViewModel
private val repository: UserRepository = mockk()

@Before
fun setUp() {
    viewModel = UserViewModel(repository)
}
```

---

## Repository 測試設定

### Mock DataSource
```kotlin
private val remoteDataSource: RemoteDataSource = mockk()
private val localDataSource: LocalDataSource = mockk()
private lateinit var repository: UserRepository

@Before
fun setUp() {
    repository = UserRepositoryImpl(remoteDataSource, localDataSource)
}
```

### Room Database（in-memory，若需要真實 DB）
```kotlin
private lateinit var database: AppDatabase

@Before
fun setUp() {
    database = Room.inMemoryDatabaseBuilder(
        ApplicationProvider.getApplicationContext(),
        AppDatabase::class.java
    ).allowMainThreadQueries().build()
}

@After
fun tearDown() {
    database.close()
}
```

---

## UseCase 測試

UseCase 通常是純函式（no framework dependency），直接測試 `invoke()`：

```kotlin
@Test
fun `invoke_withValidInput_returnsProcessedResult`() = runTest {
    // given
    coEvery { repository.getData(any()) } returns mockData
    // when
    val result = useCase(validInput)
    // then
    assertTrue(result.isSuccess)
    assertEquals(expectedOutput, result.getOrNull())
}
```

---

## MockK 常用模式

```kotlin
// Stub
every { mock.property } returns value
coEvery { mock.suspendFun() } returns value
every { mock.funWithException() } throws IOException("error")

// Verify
verify { mock.method(any()) }
coVerify { mock.suspendMethod(eq(expectedArg)) }
verify(exactly = 0) { mock.methodNotCalled() }

// Capture
val slot = slot<String>()
every { mock.method(capture(slot)) } returns Unit
// 後續 slot.captured 取得捕獲的參數

// Answer（動態回傳）
every { mock.method(any()) } answers { firstArg<String>().uppercase() }
```
